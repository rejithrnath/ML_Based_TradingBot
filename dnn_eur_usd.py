# -*- coding: utf-8 -*-
"""DNN_EUR_USD.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/13xb6qnUM5eRZscZrPdSRDADoaaQv4k1R
"""

#!pip install git+git://github.com/yhilpisch/tpqoa
import pandas as pd
import tpqoa
import datetime
import schedule


##from google.colab import drive
#drive.mount('/content/gdrive')
oanda_API='temp/oanda_API.cfg'
api = tpqoa.tpqoa(oanda_API)


# import sys
# sys.path.append('/content/gdrive/MyDrive/Algotrading/Algotrading/Colab')
# import yfinance as yf

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
plt.style.use("seaborn")
pd.set_option('display.float_format', lambda x: '%.5f' % x)

ins = api.get_instruments()
ins

from datetime import datetime, timedelta

delta_time =8


symbol = "EUR_USD"

now = datetime.utcnow()
now = now - timedelta(microseconds = now.microsecond)
past = now - timedelta(days = delta_time)
data =api.get_history(instrument =symbol, start = past, end = now,granularity = "M1", price = "M", localize = False)
data

#for NYTIME
data["NYTime"] = data.index.tz_convert("America/New_York")
data["hour"] = data.NYTime.dt.hour

# data['time']= pd.to_datetime(data['time'])

data["c"] = np.where(~data.hour.between(2, 12), np.nan, data.c) # 3. neutral in non-busy hours
data.dropna(inplace = True)

data =data.drop(['NYTime', 'hour'], axis = 1)

data.to_csv('raw.csv')
data



data["returns"] = np.log(data['c'] / data['c'].shift())

data.to_csv('raw.csv')

window = 8
long_window =21

df = data.copy()
df["dir"] = np.where(df["returns"] > 0, 1, 0)
df["sma"] = df['c'].rolling(window).mean() - df['c'].rolling(35).mean()
df["boll"] = (df['c'] - df['c'].rolling(window).mean()) / df['c'].rolling(window).std()
df["min"] = df['c'].rolling(window).min() / df['c'] - 1
df["max"] =df['c'].rolling(window).max() /df['c'] - 1
df["mom"] = df["returns"].rolling(3).mean()
df["vol"] = df["returns"].rolling(window).std()

df['20sma'] = df['c'].rolling(window=20).mean()
df['stddev'] = df['c'].rolling(window=20).std()
df['lower_band'] = df['20sma'] - (2 * df['stddev'])
df['upper_band'] = df['20sma'] + (2 * df['stddev'])
df['8dayEWM']  = df['c'].ewm(span=8 , adjust=False).mean()
df['13dayEWM'] = df['c'].ewm(span=13, adjust=False).mean()
df['21dayEWM'] = df['c'].ewm(span=21, adjust=False).mean()
df['34dayEWM'] = df['c'].ewm(span=34, adjust=False).mean()
df['55dayEWM'] = df['c'].ewm(span=55, adjust=False).mean()
df['89dayEWM'] = df['c'].ewm(span=89, adjust=False).mean()

df.dropna(inplace = True)

lags = 2

cols = []
features = ["dir", "min","sma", "max", "mom", "vol", "20sma","stddev","lower_band","upper_band","8dayEWM","13dayEWM"]
# features = ["dir"features = ["dir","sma","boll", "min", "max", "mom", "vol"], "min", "max", "mom", "vol"]

for f in features:
        for lag in range(1, lags + 1):
            col = "{}_lag_{}".format(f, lag)
            df[col] = df[f].shift(lag)
            cols.append(col)
df.dropna(inplace = True)

df

split = int(len(df)*0.66)

train = df.iloc[:split].copy()

test = df.iloc[split:].copy()

train[cols]

mu, std = train.mean(), train.std() # train set parameters (mu, std) for standardization

train_s = (train - mu) / std # standardization of train set features

train_s

import random
import numpy as np
import tensorflow as tf
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.models import Sequential
from tensorflow.keras.regularizers import l1, l2
from tensorflow.keras.optimizers import SGD
from sklearn.ensemble import RandomForestClassifier

def set_seeds(seed = 100):
    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)
    
def cw(df):
    c0, c1 = np.bincount(df["dir"])
    w0 = (1/c0) * (len(df)) / 2
    w1 = (1/c1) * (len(df)) / 2
    return {0:w0, 1:w1}

optimizer = SGD(learning_rate = 0.0001)

def create_model(hl = 2, hu = 100, dropout = False, rate = 0.3, regularize = False,
                 reg = l1(0.0005), optimizer = optimizer, input_dim = None):
    if not regularize:
        reg = None
    model = Sequential()
    model.add(Dense(hu, input_dim = input_dim, activity_regularizer = reg ,activation = "relu"))
    if dropout: 
        model.add(Dropout(rate, seed = 100))
    for layer in range(hl):
        model.add(Dense(hu, activation = "relu", activity_regularizer = reg))
        if dropout:
            model.add(Dropout(rate, seed = 100))
    model.add(Dense(1, activation = "sigmoid"))
    model.compile(loss = "binary_crossentropy", optimizer = optimizer, metrics = ["accuracy"])
    return model

set_seeds(100)
model = create_model(hl = 3, hu = 50, dropout = True, input_dim = len(cols))
model.fit(x = train_s[cols], y = train["dir"], epochs = 50, verbose = False,
        shuffle = False, class_weight = cw(train))
model.evaluate(train_s[cols], train["dir"]) # evaluate the fit on the train set
# model = RandomForestClassifier(criterion='entropy', n_estimators=80,max_depth=8)
# model.fit(train_s[cols], train["dir"])





pred = model.predict(train_s[cols]) # prediction (probabilities)
pred

# plt.hist(pred, bins = 50)
# plt.show()

test_s = (test[cols] - mu) / std # standardization of test set features (with train set parameters!!!)

model.evaluate(test_s[cols], test["dir"])

pred = model.predict(test_s[cols])
pred

# plt.hist(pred, bins = 50);

test["proba"] = model.predict(test_s[cols])

test["position"] = np.where(test.proba < 0.47, -1, np.nan) # 1. short where proba < 0.48

test["position"] = np.where(test.proba > 0.53, 1, test.position) # 2. long where proba > 0.52

test.index = test.index.tz_convert("UTC")
test["NYTime"] = test.index.tz_convert("America/New_York")
test["hour"] = test.NYTime.dt.hour

test["position"] = np.where(~test.hour.between(2, 12), 0, test.position) # 3. neutral in non-busy hours

test["position"] = test.position.ffill().fillna(0) # 4. in all other cases: hold position

test.position.value_counts(dropna = False)

test["strategy"] = test["position"] * test["returns"]

test["creturns"] = test["returns"].cumsum().apply(np.exp)
test["cstrategy"] = test["strategy"].cumsum().apply(np.exp)

# test[["creturns", "cstrategy"]].plot(figsize = (12, 8))
# plt.show()

ptc = 0.000059

test["trades"] = test.position.diff().abs()

test.trades.value_counts()

test["strategy_net"] = test.strategy - test.trades * ptc

test["cstrategy_net"] = test["strategy_net"].cumsum().apply(np.exp)

# test[["creturns", "cstrategy", "cstrategy_net"]].plot(figsize = (12, 8))
# plt.show()

model

model.save("DNN_model")

import pickle

params = {"mu":mu, "std":std}

pickle.dump(params, open("params.pkl", "wb"))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# Loading the model
import tensorflow.keras
model = tensorflow.keras.models.load_model("DNN_model")

# Loading mu and std
import pickle
import math 
params = pickle.load(open("params.pkl", "rb"))
mu = params["mu"]
std = params["std"]

class DNNTrader(tpqoa.tpqoa):
    def __init__(self, conf_file, instrument, bar_length, window, lags, model, mu, std, units):
        super().__init__(conf_file)
        self.instrument = instrument
        self.bar_length = pd.to_timedelta(bar_length)
        self.tick_data = pd.DataFrame()
        self.raw_data = None
        self.data = None 
        self.last_bar = None
        self.units = units
        self.position = 0
        self.diff = 0
        self.tp = [0]
        self.tp_cum = 0
        self.profits = []
        
        #*****************add strategy-specific attributes here******************
        self.window = window
        self.lags = lags
        self.model = model
        self.mu = mu
        self.std = std
        
        #************************************************************************
    
    def get_most_recent(self, days = 5):
        while True:
            time.sleep(2)
            now = datetime.utcnow()
            now = now - timedelta(microseconds = now.microsecond)
            past = now - timedelta(days = days)
            df = self.get_history(instrument = self.instrument, start = past, end = now,
                                   granularity = "S5", price = "M", localize = False).c.dropna().to_frame()
            df.rename(columns = {"c":self.instrument}, inplace = True)
            df = df.resample(self.bar_length, label = "right").last().dropna().iloc[:-1]
            self.raw_data = df.copy()
            self.last_bar = self.raw_data.index[-1]
            if pd.to_datetime(datetime.utcnow()).tz_localize("UTC") - self.last_bar < self.bar_length:
                self.start_time = pd.to_datetime(datetime.utcnow()).tz_localize("UTC") # NEW -> Start Time of Trading Session
                break
                
    def on_success(self, time, bid, ask):
        print(self.ticks, end = " ")
        
        recent_tick = pd.to_datetime(time)
        df = pd.DataFrame({self.instrument:(ask + bid)/2}, 
                          index = [recent_tick])
        self.tick_data = self.tick_data.append(df)
        
        if recent_tick - self.last_bar > self.bar_length:
            self.resample_and_join()
            self.define_strategy()
            self.execute_trades()
            
        if int(datetime.now().hour) > 17 :
            print('Stopped!')
            self.stop_stream = True
            
    
    def resample_and_join(self):
        self.raw_data = self.raw_data.append(self.tick_data.resample(self.bar_length, 
                                                                  label="right").last().ffill().iloc[:-1])
        self.tick_data = self.tick_data.iloc[-1:]
        self.last_bar = self.raw_data.index[-1]
    
    def define_strategy(self): # "strategy-specific"
        df = self.raw_data.copy()
        
        #******************** define your strategy here ************************
        #create features
        df = df.append(self.tick_data) # append latest tick (== open price of current bar)
        df["returns"] = np.log(df[self.instrument] / df[self.instrument].shift())
        df["dir"] = np.where(df["returns"] > 0, 1, 0)
        df["sma"] = df[self.instrument].rolling(self.window).mean() - df[self.instrument].rolling(35).mean()
        df["boll"] = (df[self.instrument] - df[self.instrument].rolling(self.window).mean()) / df[self.instrument].rolling(self.window).std()
        df["min"] = df[self.instrument].rolling(self.window).min() / df[self.instrument] - 1
        df["max"] = df[self.instrument].rolling(self.window).max() / df[self.instrument] - 1
        df["mom"] = df["returns"].rolling(3).mean()
        df["vol"] = df["returns"].rolling(self.window).std()
        df['20sma'] = df[self.instrument].rolling(window=20).mean()
        df['stddev'] = df[self.instrument].rolling(window=20).std()
        df['lower_band'] = df['20sma'] - (2 * df['stddev'])
        df['upper_band'] = df['20sma'] + (2 * df['stddev'])
        df['8dayEWM']  = df[self.instrument].ewm(span=8 , adjust=False).mean()
        df['13dayEWM'] = df[self.instrument].ewm(span=13, adjust=False).mean()
        df['21dayEWM'] = df[self.instrument].ewm(span=21, adjust=False).mean()
        df['34dayEWM'] = df[self.instrument].ewm(span=34, adjust=False).mean()
        df['55dayEWM'] = df[self.instrument].ewm(span=55, adjust=False).mean()
        df['89dayEWM'] = df[self.instrument].ewm(span=89, adjust=False).mean()
        

        df.dropna(inplace = True)
        
        # create lags
        self.cols = []
        features = ["dir", "min","sma", "max", "mom", "vol", "20sma","stddev","lower_band","upper_band","8dayEWM","13dayEWM"]
        for f in features:
            for lag in range(1, self.lags + 1):
                col = "{}_lag_{}".format(f, lag)
                df[col] = df[f].shift(lag)
                self.cols.append(col)
        df.dropna(inplace = True)
        
        # standardization
        df_s = (df - self.mu) / self.std
        # predict
        df["proba"] = self.model.predict(df_s[self.cols])
        

        #determine positions
        df = df.loc[self.start_time:].copy() # starting with first live_stream bar (removing historical bars)
        df["position"] = np.where(df.proba < 0.47, -1, np.nan)
        df["position"] = np.where(df.proba > 0.53, 1, df.position)
        df["position"] = df.position.ffill().fillna(0) # start with neutral position if no strong signal
        #***********************************************************************
        
        self.data = df.copy()
    
    def execute_trades(self):

         
            
        if self.data["position"].iloc[-1] == 1:
            if self.position == 0:
                order = self.create_order(self.instrument, self.units, suppress = True, ret = True)
                self.report_trade(order, "GOING LONG")
            elif self.position == -1:
                order = self.create_order(self.instrument, self.units * 2, suppress = True, ret = True)
                self.report_trade(order, "GOING LONG")
            self.position = 1
            
        elif self.data["position"].iloc[-1] == -1: 
            if self.position == 0:
                order = self.create_order(self.instrument, -self.units, suppress = True, ret = True)
                self.report_trade(order, "GOING SHORT")
            elif self.position == 1:
                order = self.create_order(self.instrument, -self.units * 2, suppress = True, ret = True)
                self.report_trade(order, "GOING SHORT")
            self.position = -1
            
        elif self.data["position"].iloc[-1] == 0: 
            if self.position == -1:
                order = self.create_order(self.instrument, self.units, suppress = True, ret = True)
                self.report_trade(order, "GOING NEUTRAL")
            elif self.position == 1:
                order = self.create_order(self.instrument, -self.units, suppress = True, ret = True)
                self.report_trade(order, "GOING NEUTRAL")
            self.position = 0
    

    def report_trade(self, pos, order):
        ''' Prints, logs and sends trade data.
        '''
        out = '\n\n' + 80 * '=' + '\n'
        out += '*** GOING {} *** \n'.format(pos) + '\n'
        out += str(order) + '\n'
        out += 80 * '=' + '\n'
        print(out)

trader = DNNTrader(oanda_API, symbol, bar_length = "1min",
                   window = window, lags = lags, model = model, mu = mu, std = std, units = 10000)

# trader.stream_data(trader.instrument)
trading_time = ["07"]


def trader_stream_func():
    trader.get_most_recent()
    trader.stream_data(trader.instrument)
    print('Exited')
    if trader.position != 0:
        close_order = trader.create_order(trader.instrument, units = -trader.position * trader.units,
                                        suppress = True, ret = True) 
        trader.report_trade(close_order, "GOING NEUTRAL")
        trader.position = 0    

    
# trader_stream_func()
try:
    
    for x in trading_time:
        schedule.every().monday.at(str(x)+"00").do(trader_stream_func)
        schedule.every().tuesday.at(str(x)+"00").do(trader_stream_func)
        schedule.every().wednesday.at(str(x)+"00").do(trader_stream_func)
        schedule.every().thursday.at(str(x)+"00").do(trader_stream_func)
        schedule.every().friday.at(str(x)+"00").do(trader_stream_func)

except Exception:
        pass
       


while True:
    schedule.run_pending()
    time.sleep(1)    


