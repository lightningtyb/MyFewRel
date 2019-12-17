import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
import math

class Embedding(nn.Module):

    def __init__(self, word_vec_mat, max_length, word_embedding_dim=50, pos_embedding_dim=5):
        nn.Module.__init__(self)

        self.max_length = max_length
        self.word_embedding_dim = word_embedding_dim
        self.pos_embedding_dim = pos_embedding_dim
        
        # Word embedding
        # unk = torch.randn(1, word_embedding_dim) / math.sqrt(word_embedding_dim)
        # blk = torch.zeros(1, word_embedding_dim)
        word_vec_mat = torch.from_numpy(word_vec_mat)#[400002,50]
        self.word_embedding = nn.Embedding(word_vec_mat.shape[0], self.word_embedding_dim, padding_idx=word_vec_mat.shape[0] - 1)
        self.word_embedding.weight.data.copy_(word_vec_mat)

        # Position Embedding
        self.pos1_embedding = nn.Embedding(2 * max_length, pos_embedding_dim, padding_idx=0)
        self.pos2_embedding = nn.Embedding(2 * max_length, pos_embedding_dim, padding_idx=0)

    def forward(self, inputs):
        word = inputs['word']#[100,128] each token's id
        pos1 = inputs['pos1']#[100,128] dis of each token correspodding to target enties
        pos2 = inputs['pos2']

        #self.word_embedding(word) [100,128,50]
        #pos1_embedding(pos1) [100,128,5]
        #x[100,128,60]
        x = torch.cat([self.word_embedding(word),
                            self.pos1_embedding(pos1),
                            self.pos2_embedding(pos2)], 2)
        # print(type(self.word_embedding(word)))

        return x


class EmbeddingWithSummary(nn.Module):

    def __init__(self, word_vec_mat, max_length, word_embedding_dim=50, pos_embedding_dim=5):
        nn.Module.__init__(self)

        self.max_length = max_length
        self.word_embedding_dim = word_embedding_dim
        self.pos_embedding_dim = pos_embedding_dim

        # Word embedding
        # unk = torch.randn(1, word_embedding_dim) / math.sqrt(word_embedding_dim)
        # blk = torch.zeros(1, word_embedding_dim)
        word_vec_mat = torch.from_numpy(word_vec_mat)  # [400002,50]
        self.word_embedding = nn.Embedding(word_vec_mat.shape[0], self.word_embedding_dim,
                                           padding_idx=word_vec_mat.shape[0] - 1)
        self.word_embedding.weight.data.copy_(word_vec_mat)

        # Position Embedding
        self.pos1_embedding = nn.Embedding(2 * max_length, pos_embedding_dim, padding_idx=0)
        self.pos2_embedding = nn.Embedding(2 * max_length, pos_embedding_dim, padding_idx=0)

    def forward(self, inputs):
        word = inputs['word']  # [100,128] each token's id
        pos1 = inputs['pos1']  # [100,128] dis of each token correspodding to target enties
        pos2 = inputs['pos2']
        smry1 = inputs['smry1']
        smry2 = inputs['smry2']


        # self.word_embedding(word) [100,128,50]
        # pos1_embedding(pos1) [100,128,5]
        # x[100,128,60] - > [100,128,50*3+5*2=160]
        x = torch.cat([self.word_embedding(word),
                       self.pos1_embedding(pos1),
                       self.pos2_embedding(pos2),
                      self.word_embedding(smry1),
                      self.word_embedding(smry2)], 2)
        # print(type(self.word_embedding(word)))

        return x
