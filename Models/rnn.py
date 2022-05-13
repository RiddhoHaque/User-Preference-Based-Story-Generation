# -*- coding: utf-8 -*-
"""rnn.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1iLJLgeaz6c8wDMpz0TaB4gHz9rc3nfGh
"""

!pip install torchdata

from google.colab import drive
import os
drive.mount('/content/drive/')

# Commented out IPython magic to ensure Python compatibility.
# %cd drive/My\ Drive/NLP Spring 22/Project/

import torch
from torch import nn
from torch import optim
from torchtext.data.utils import get_tokenizer
from torchtext.datasets import AG_NEWS
from torchtext.datasets import WikiText103
from torchtext.vocab import build_vocab_from_iterator
import torch.nn.functional as F

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(device)

tokenizer = get_tokenizer('basic_english')
train_iter = WikiText103(split='train')

def yield_tokens(data_iter):
  for text in data_iter:
    yield tokenizer(text)

vocab = build_vocab_from_iterator(yield_tokens(train_iter), specials=["<unk>", "<cls>", "<SOS>", "<EOS>"])
vocab.set_default_index(vocab["<unk>"])

text_pipeline = lambda x: vocab(tokenizer(x))
label_pipeline = lambda x: vocab(tokenizer(x))

def sent2TensorOld(sent='my name is mashrur'):
  snt = text_pipeline(sent)
  snt = snt + vocab(["<EOS>"])

  return torch.tensor(snt, dtype=torch.long, device=device).view(-1, 1)

def ind2word(x):
  return vocab.lookup_token(x)

def sent2Tensor(x):
  return torch.tensor(text_pipeline(x), dtype=torch.int64).unsqueeze(0).view(-1, 1).to(device)

import csv
import math
import random

filename = 'data/Context_to_Option_Mixed.csv'
xx = []
yy = []
dats = []

with open(filename, 'r') as f:
  reader = csv.reader(f, delimiter=',')
  header = next(reader)

  for row in reader:
    genre = str(row[0]).strip()
    rep_genre = '<' + genre + '>'
    n_genre = ' < ' + genre + ' > '
    #n_genre = ''
    dats.append((
        row[1].replace('<', ' <').replace('>', '> ').replace('  ', ' ').replace(rep_genre, n_genre).strip(),
        row[2].replace('<', ' <').replace('>', '> ').replace('  ', ' ').strip()
    ))
    
random.shuffle(dats)

for ii in dats:
  xx.append(ii[0])
  yy.append(ii[1])

def create_split():
  train_x = []
  train_y = []
  test_x = []
  test_y = []
  val_x = []
  val_y = []

  ln = len(xx)
  tr_ln = int(.8*ln)
  tst_ln = int(0.15*ln)

  for i in range(tr_ln):
    train_x.append(xx[i])
    train_y.append(yy[i])

  for i in range(tr_ln, tr_ln+tst_ln):
    test_x.append(xx[i])
    test_y.append(yy[i])

  for i in range(tr_ln+tst_ln, ln):
    val_x.append(xx[i])
    val_y.append(yy[i])


  return train_x, train_y, test_x, test_y, val_x, val_y

class Dataset(torch.utils.data.Dataset):
  def __init__(self, inp, trg):
    self.input = [text_pipeline(x) for x in inp]
    self.target = [label_pipeline(x) for x in trg]
    self.input_original = inp
    self.target_original = trg

  def __getitem__(self, idx):
    data = {'X': torch.tensor(self.input[idx], dtype=torch.int64).to(device=device), 
            'Y': torch.tensor(self.target[idx], dtype=torch.int64).to(device=device),
            'Y_o': self.target_original[idx]}
    return data

class EncoderRNN(nn.Module):
  def __init__(self, input_size, hidden_size):
    super(EncoderRNN, self).__init__()

    self.hidden_size = hidden_size
    self.input_size = input_size

    self.embedding_layer = nn.Embedding(self.input_size, self.hidden_size)
    self.rnn = nn.RNN(self.hidden_size, self.hidden_size)
    encoder_layer = nn.TransformerEncoderLayer(d_model=self.hidden_size, nhead=1)
    self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=1)


  def forward(self, input, hidden):
    embed = self.embedding_layer(input).view(1, 1, -1)
    out, h = self.rnn(embed, hidden)
    out = self.transformer_encoder(out)
    return out, h

  def initHidden(self, device):
    return torch.zeros(1, 1, self.hidden_size).to(device=device)

DROPOUT = 0.1
MX_LN = 5000

class DecoderRNN(nn.Module):
  def __init__(self, hidden_size, output_size, max_length, dropout):
    super(DecoderRNN, self).__init__()
    self.hidden_size = hidden_size
    self.output_size = output_size
    self.max_length = max_length
    self.dropout = dropout

    self.embedding_layer = nn.Embedding(self.output_size, self.hidden_size)
    self.attention_layer = nn.Linear(2*self.hidden_size, self.max_length)
    self.attention_out = nn.Linear(2*self.hidden_size, self.hidden_size)

    self.dropout = nn.Dropout(self.dropout)
    self.rnn = nn.RNN(self.hidden_size, self.hidden_size)
    self.output_layer = nn.Linear(self.hidden_size, self.output_size)
    #decoder_layer = nn.TransformerDecoderLayer(d_model=self.hidden_size, nhead=1)
    #self.transformer_decoder = nn.TransformerDecoder(decoder_layer, num_layers=1)


  def forward(self, input, hidden, encoder_out):
    embeded = self.dropout(self.embedding_layer(input).view(1, 1, -1))
    att_temp = self.attention_layer(torch.cat((embeded[0], hidden[0]), 1))
    att_w = F.softmax(att_temp, 1)
    att_temp = torch.bmm(att_w.unsqueeze(0), encoder_out.unsqueeze(0))
    att_temp = torch.cat((embeded[0], att_temp[0]), 1)
    att_temp = self.attention_out(att_temp).unsqueeze(0)

    out = F.relu(att_temp)
    out, h = self.rnn(out, hidden)

    #memory = encoder_out[0].view(1, 1, -1)
    #out = self.transformer_decoder(out, memory)

    out = F.log_softmax(self.output_layer(out[0]), 1)
    return out, h, att_w

  def initHidden(self, device):
    return torch.zeros(1, 1, self.hidden_size).to(device=device)

MAX_LENGTH = 5000
SOS = vocab(["<SOS>"])[0]
EOS = vocab(["<EOS>"])[0]
CLS = vocab(["<cls>"])[0]

teacher_ratio = 0.5


def train_sgd(inp, trg, encoder, decoder, encoder_opt, decoder_opt, 
                   criterion, max_length = MAX_LENGTH):
  h = encoder.initHidden(device)
  loss = 0
  encoder_opt.zero_grad()
  decoder_opt.zero_grad()

  encoder_out = torch.zeros(max_length, encoder.hidden_size, device=device)
  
  for i, x in enumerate(inp):
    out, h = encoder(x, h)
    encoder_out[i] = out[0, 0]
    

  dec_inp = torch.tensor([[SOS]], device=device)
  use_forcing = True if random.random() < teacher_ratio else False

  if use_forcing:
    for i, x in enumerate(trg):
      out, h, att_w = decoder(dec_inp, h, encoder_out)
      loss += criterion(out, torch.tensor([trg[i]]).to(device=device))
      dec_inp = torch.tensor([trg[i]]).to(device=device)
  else:
    for i, x in enumerate(trg):
      out, h, att_w = decoder(dec_inp, h, encoder_out)
      topv, topi = out.topk(1)
      dec_inp = topi.squeeze().detach()
      loss += criterion(out, torch.tensor([trg[i]]).to(device=device))
      if dec_inp.item() == EOS:
        break
  
  loss.backward()
  encoder_opt.step()
  decoder_opt.step()

  return loss.item()/trg.size(0)

def val_instance(inp, trg, encoder, decoder, 
                 criterion, max_length = MAX_LENGTH):
  with torch.no_grad():
    words = []
    h = encoder.initHidden(device)
    loss = 0

    encoder_out = torch.zeros(max_length, encoder.hidden_size, device=device)
    
    for i, x in enumerate(inp):
      out, h = encoder(x, h)
      encoder_out[i] += out[0, 0]
      

    dec_inp = torch.tensor([[SOS]], device=device)

    for i, x in enumerate(trg):
      out, h, att_w = decoder(dec_inp, h, encoder_out)
      topv, topi = out.topk(1)
      dec_inp = topi.squeeze().detach()
      if topi.item() == EOS:
        words.append('<EOS>')
        break
      else:
        words.append(ind2word(topi.item()))
      loss += criterion(out, torch.tensor([trg[i]]).to(device=device))
      if dec_inp.item() == EOS:
        break

    return loss.item()/trg.size(0), ' '.join(words)

def train(encoder, decoder, train_data, encoder_opt, decoder_opt, criterion, lr=0.01):
  all_loss = []

  for data in train_data:
    loss = train_sgd(data['X'], data['Y'], encoder, decoder, encoder_opt,
                     decoder_opt, criterion)

    all_loss.append(loss)
  
  return all_loss

from nltk.translate.bleu_score import SmoothingFunction, corpus_bleu, sentence_bleu

def bleu(ref, gen):
  ref[0] = '<SOS> ' + ref[0] + ' <EOS>'
  ref_bleu = []
  gen_bleu = []
  for l in gen:
    gen_bleu.append(l.split())
  for i,l in enumerate(ref):
    ref_bleu.append([l.split()])
  cc = SmoothingFunction()
  score_bleu = corpus_bleu(ref_bleu, gen_bleu, weights=(0, 1, 0, 0), smoothing_function=cc.method4)
  return score_bleu

def validation(encoder, decoder, val_data, criterion, lr=0.01):
  all_loss = []
  all_bleu = []
  for data in val_data:
    loss, sent = val_instance(data['X'], data['Y'], encoder, decoder, criterion)

    all_loss.append(loss)
    all_bleu.append(bleu([sent], [data['Y_o']]))
  
  return all_loss, all_bleu

def getSampleX():
  return ['<SOS> lol <cls> my name is mashrur <EOS>']
def getSampleY():
  return ['<SOS> lol1 <cls> lol2 <cls> lol3 <cls> lol4 <EOS>']

from statistics import mean 

train_x, train_y, test_x, test_y, val_x, val_y = create_split()
train_data = Dataset(train_x, train_y)
test_data = Dataset(test_x, test_y)
val_data = Dataset(val_x, val_y)

inp_size = vocab.__len__()
out_size = vocab.__len__()
hidden_size = 256
learning_rate = 0.01
#encoder = EncoderRNN(inp_size, hidden_size).to(device)
#decoder = DecoderRNN(hidden_size, out_size, MAX_LENGTH, dropout=0.1).to(device)

def comp_train(epochs = [2, 3, 5, 7, 9, 11, 13, 15]):
  train_losses = []
  val_losses = []
  bleu_scores = []
  best_bleu_score = -10000
  best_encoder = None
  best_decoder = None

  for ep in epochs:
    train_losses_ep = []
    val_losses_ep = []
    bleu_scores_ep = []
    encoder = EncoderRNN(inp_size, hidden_size).to(device)
    decoder = DecoderRNN(hidden_size, out_size, MAX_LENGTH, dropout=0.1).to(device)
    encoder_opt = optim.SGD(encoder.parameters(), lr=learning_rate)
    decoder_opt = optim.SGD(decoder.parameters(), lr=learning_rate)
    criterion = nn.NLLLoss()

    for it in range(ep):
      train_loss = train(encoder, decoder, train_data, encoder_opt, decoder_opt, criterion, lr=learning_rate)
      train_loss_avg = mean(train_loss)

      val_loss, all_bleu = validation(encoder, decoder, test_data, criterion, lr=learning_rate) # here replace train_data with test_data iterator
      val_loss_avg = mean(val_loss)
      bleu_score_avg = mean(all_bleu)

      if bleu_score_avg > best_bleu_score:
        best_bleu_score = bleu_score_avg
        best_encoder = encoder
        best_decoder = decoder

      train_losses_ep.append(train_loss_avg)
      val_losses_ep.append(val_loss_avg)
      bleu_scores_ep.append(bleu_score_avg)
    train_losses.append(mean(train_losses_ep))
    val_losses.append(mean(val_losses_ep))
    bleu_scores.append(mean(bleu_scores_ep))

    print('Epoch: {}, Train Loss: {}, Val Loss: {}, BLEU: {}'.format(ep, 
                                                                     train_losses[-1],
                                                                     val_losses[-1],
                                                                     bleu_scores[-1]))
  return train_losses, val_losses, bleu_scores, best_encoder, best_decoder

epochs = [1, 2, 3, 5, 7, 9]


train_losses, val_losses, bleu_scores, encoder, decoder = comp_train(epochs)

print(bleu_scores)

"""# Plot Data"""

import matplotlib.pyplot as plt
plt.switch_backend('agg')
import matplotlib.ticker as ticker
import numpy as np


def showPlot(points, epochs, filename, scorename):
    #plt.figure()
    #fig, ax = plt.subplots()
    # this locator puts ticks at regular intervals
    #loc = ticker.MultipleLocator(base=0.2)
    #ax.yaxis.set_major_locator(loc)
    plt.xlabel('Number of epochs')
    plt.ylabel(scorename)
    plt.plot(epochs, points)

    plt.savefig(filename)

bleu_scores = [x*100 for x in bleu_scores]

showPlot(bleu_scores, epochs, 'plots/rnnbleu.png', 'BLEU')
showPlot(val_losses, epochs, 'plots/rnnval.png', 'Test Loss')

"""# Saving Trained Model"""

# Commented out IPython magic to ensure Python compatibility.
# %ls

torch.save(encoder.state_dict(), 'models/encoderRNN.pt')

torch.save(decoder.state_dict(), 'models/decoderRNN.pt')

load_encoder = EncoderRNN(inp_size, hidden_size).to(device)
load_decoder = DecoderRNN(hidden_size, out_size, MAX_LENGTH, dropout=0.1).to(device)

load_encoder.load_state_dict(torch.load('models/encoderRNN.pt'))
load_decoder.load_state_dict(torch.load('models/decoderRNN.pt'))

"""# Code for Prediction"""

def trigram_block(words, lst):
  ret = []
  fin0 = lst[-2]
  fin1 = lst[-1]
  for i in range(len(words)-2):
    if (words[i] == fin0) and (words[i+1] == fin1):
      ret.append(words[i+2])

  for x in ret:
    if x in lst:
      lst.remove(x)
  
  return lst

def get_prediction(encoder, decoder, sentence, max_length = MAX_LENGTH):
  with torch.no_grad():
    words = []
    taken = []
    h = encoder.initHidden(device)
    inp = sent2Tensor(sentence)
    inp_ln = inp.size()[0]
    encoder_out = torch.zeros(max_length, encoder.hidden_size, device=device)
    
    for i, x in enumerate(inp):
      out, h = encoder(x, h)
      encoder_out[i] += out[0, 0]

    dec_inp = torch.tensor([[SOS]], device=device)

    for i in range(MAX_LENGTH):
      out, h, att_w = decoder(dec_inp, h, encoder_out)
      kk = 10
      topv, topi = out.topk(kk)

      
      lst = topi.tolist()[0]
      topmost = EOS

      lst = trigram_block(taken, lst)
      
      
      
      for j in range(len(lst)):
        if lst[j] not in taken:
          topmost = lst[j]
          break
      
      
      '''
      if len(lst) > 0:
        topmost = lst[0]
      '''


      if topmost == EOS:
        words.append('<EOS>')
        break
      else:
        words.append(ind2word(topmost))
        taken.append(topmost)
      
      
      #dec_inp = torch.tensor(lst[0]).to(device=device)
      dec_inp = torch.tensor(topmost).to(device=device)
    return ' '.join(words)

inps = []
with open('inps.txt', 'r') as f:
  inps = f.readlines()
  inps = [x.replace('<', ' <').replace('>', '> ').replace('  ', ' ').strip() for x in inps]
  print(inps)

for x in inps:
  xx = get_prediction(load_encoder, load_decoder, sentence=x)
  print(xx)

