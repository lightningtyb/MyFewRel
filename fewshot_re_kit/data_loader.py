import torch
import torch.utils.data as data
import os
import numpy as np
import random
import json

class FewRelDataset(data.Dataset):
    """
    FewRel Dataset
    """
    def __init__(self, name, encoder, N, K, Q, na_rate, root):
        self.root = root
        path = os.path.join(root, name + ".json")
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            assert(0)
        self.json_data = json.load(open(path))
        self.classes = list(self.json_data.keys())
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder

    def __getraw__(self, item):
        word, pos1, pos2, mask = self.encoder.tokenize(item['tokens'],
            item['h'][2][0],
            item['t'][2][0])#mask的长度为句子编码长度，128，其中[:indexed_tokens] indexed_tokens=min(128,)
        return word, pos1, pos2, mask #word是token的在glove词典中对应的id,pos1/pos2是每个token相对头尾实体的第一个索引的相对位置，mask[:indexed_token]为1

    def __additem__(self, d, word, pos1, pos2, mask):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)

    def __getitem__(self, index):
        target_classes = random.sample(self.classes, self.N)
        support_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [] }
        query_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [] }
        query_label = []
        Q_na = int(self.na_rate * self.Q)
        na_classes = list(filter(lambda x: x not in target_classes,  
            self.classes))

        for i, class_name in enumerate(target_classes):#从target_classes（N个）中，每个class中，随机选K+Q个关系类别
            indices = np.random.choice(
                    list(range(len(self.json_data[class_name]))), 
                    self.K + self.Q, False)
            count = 0#统计样本个数
            for j in indices:#将word,pos1,pos2转为id
                word, pos1, pos2, mask = self.__getraw__(
                        self.json_data[class_name][j])
                word = torch.tensor(word).long()
                pos1 = torch.tensor(pos1).long()
                pos2 = torch.tensor(pos2).long()
                mask = torch.tensor(mask).long()
                if count < self.K:#如果小于K个，继续补充support_set，大于构建query_set
                    self.__additem__(support_set, word, pos1, pos2, mask)
                else:
                    self.__additem__(query_set, word, pos1, pos2, mask)
                count += 1

            query_label += [i] * self.Q#label用0-(N-1)的数字表示,每次增加Q个label

        # NA
        for j in range(Q_na):#若有na，则在K个query后再增加其他class的样本，label是N
            cur_class = np.random.choice(na_classes, 1, False)[0]
            index = np.random.choice(
                    list(range(len(self.json_data[cur_class]))),
                    1, False)[0]
            word, pos1, pos2, mask = self.__getraw__(
                    self.json_data[cur_class][index])
            word = torch.tensor(word).long()
            pos1 = torch.tensor(pos1).long()
            pos2 = torch.tensor(pos2).long()
            mask = torch.tensor(mask).long()
            self.__additem__(query_set, word, pos1, pos2, mask)
        query_label += [self.N] * Q_na

        return support_set, query_set, query_label
    
    def __len__(self):
        return 1000000000

def collate_fn(data):
    batch_support = {'word': [], 'pos1': [], 'pos2': [], 'mask': []}
    batch_query = {'word': [], 'pos1': [], 'pos2': [], 'mask': []}
    batch_label = []
    support_sets, query_sets, query_labels = zip(*data)
    for i in range(len(support_sets)):
        for k in support_sets[i]:
            batch_support[k] += support_sets[i][k]
        for k in query_sets[i]:
            batch_query[k] += query_sets[i][k]
        batch_label += query_labels[i]
    for k in batch_support:
        batch_support[k] = torch.stack(batch_support[k], 0)
    for k in batch_query:
        batch_query[k] = torch.stack(batch_query[k], 0)
    batch_label = torch.tensor(batch_label)
    return batch_support, batch_query, batch_label

def get_loader(name, encoder, N, K, Q, batch_size, 
        num_workers=8, collate_fn=collate_fn, na_rate=0, root='./data'):
    dataset = FewRelDataset(name, encoder, N, K, Q, na_rate, root)
    data_loader = data.DataLoader(dataset=dataset,
            batch_size=batch_size,
            shuffle=False,
            pin_memory=True,
            num_workers=num_workers,
            collate_fn=collate_fn)
    return iter(data_loader)

class FewRelDatasetPair(data.Dataset):
    """
    FewRel Pair Dataset
    """
    def __init__(self, name, encoder, N, K, Q, na_rate, root):
        self.root = root
        path = os.path.join(root, name + ".json")
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            assert(0)
        self.json_data = json.load(open(path))
        self.classes = list(self.json_data.keys())
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder
        self.max_length = encoder.max_length

    def __getraw__(self, item):
        word = self.encoder.tokenize(item['tokens'],
            item['h'][2][0],
            item['t'][2][0])
        return word 

    def __additem__(self, d, word, pos1, pos2, mask):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)

    def __getitem__(self, index):
        target_classes = random.sample(self.classes, self.N)
        support = []
        query = []
        fusion_set = {'word': [], 'mask': [], 'seg': []}
        query_label = []
        Q_na = int(self.na_rate * self.Q)
        na_classes = list(filter(lambda x: x not in target_classes,  
            self.classes))

        for i, class_name in enumerate(target_classes):
            indices = np.random.choice(
                    list(range(len(self.json_data[class_name]))), 
                    self.K + self.Q, False)
            count = 0
            for j in indices:
                word  = self.__getraw__(
                        self.json_data[class_name][j])
                if count < self.K:
                    support.append(word)
                else:
                    query.append(word)
                count += 1

            query_label += [i] * self.Q

        # NA
        for j in range(Q_na):
            cur_class = np.random.choice(na_classes, 1, False)[0]
            index = np.random.choice(
                    list(range(len(self.json_data[cur_class]))),
                    1, False)[0]
            word = self.__getraw__(
                    self.json_data[cur_class][index])
            query.append(word)
        query_label += [self.N] * Q_na


        for word_query in query:
            for word_support in support:
                SEP = self.encoder.tokenizer.convert_tokens_to_ids(['[SEP]'])
                CLS = self.encoder.tokenizer.convert_tokens_to_ids(['[CLS]'])
                new_word = CLS + word_support + SEP + word_query + SEP
                word_tensor = torch.zeros((self.max_length)).long()
                for i in range(min(self.max_length, len(new_word))):
                    word_tensor[i] = new_word[i]
                mask_tensor = torch.zeros((self.max_length)).long()
                mask_tensor[:min(self.max_length, len(new_word))] = 1
                seg_tensor = torch.ones((self.max_length)).long()
                seg_tensor[:min(self.max_length, len(word_support) + 1)] = 0
                fusion_set['word'].append(word_tensor)
                fusion_set['mask'].append(mask_tensor)
                fusion_set['seg'].append(seg_tensor)

        return fusion_set, query_label
    
    def __len__(self):
        return 1000000000

def collate_fn_pair(data):
    batch_set = {'word': [], 'seg': [], 'mask': []}
    batch_label = []
    fusion_sets, query_labels = zip(*data)
    for i in range(len(fusion_sets)):
        for k in fusion_sets[i]:
            batch_set[k] += fusion_sets[i][k]
        batch_label += query_labels[i]
    for k in batch_set:
        batch_set[k] = torch.stack(batch_set[k], 0)
    batch_label = torch.tensor(batch_label)
    return batch_set, batch_label

def get_loader_pair(name, encoder, N, K, Q, batch_size, 
        num_workers=8, collate_fn=collate_fn_pair, na_rate=0, root='./data'):
    dataset = FewRelDatasetPair(name, encoder, N, K, Q, na_rate, root)
    data_loader = data.DataLoader(dataset=dataset,
            batch_size=batch_size,
            shuffle=False,
            pin_memory=True,
            num_workers=num_workers,
            collate_fn=collate_fn)
    return iter(data_loader)

class FewRelUnsupervisedDataset(data.Dataset):
    """
    FewRel Unsupervised Dataset
    """
    def __init__(self, name, encoder, N, K, Q, na_rate, root):
        self.root = root
        path = os.path.join(root, name + ".json")
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            assert(0)
        self.json_data = json.load(open(path))
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder

    def __getraw__(self, item):
        word, pos1, pos2, mask = self.encoder.tokenize(item['tokens'],
            item['h'][2][0],
            item['t'][2][0])
        return word, pos1, pos2, mask 

    def __additem__(self, d, word, pos1, pos2, mask):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)

    def __getitem__(self, index):
        total = self.N * self.K
        support_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [] }

        indices = np.random.choice(list(range(len(self.json_data))), total, False)
        for j in indices:
            word, pos1, pos2, mask = self.__getraw__(
                    self.json_data[j])
            word = torch.tensor(word).long()
            pos1 = torch.tensor(pos1).long()
            pos2 = torch.tensor(pos2).long()
            mask = torch.tensor(mask).long()
            self.__additem__(support_set, word, pos1, pos2, mask)

        return support_set
    
    def __len__(self):
        return 1000000000

def collate_fn_unsupervised(data):
    batch_support = {'word': [], 'pos1': [], 'pos2': [], 'mask': []}
    support_sets = data
    for i in range(len(support_sets)):
        for k in support_sets[i]:
            batch_support[k] += support_sets[i][k]
    for k in batch_support:
        batch_support[k] = torch.stack(batch_support[k], 0)
    return batch_support

def get_loader_unsupervised(name, encoder, N, K, Q, batch_size, 
        num_workers=8, collate_fn=collate_fn_unsupervised, na_rate=0, root='./data'):
    dataset = FewRelUnsupervisedDataset(name, encoder, N, K, Q, na_rate, root)
    data_loader = data.DataLoader(dataset=dataset,
            batch_size=batch_size,
            shuffle=False,
            pin_memory=True,
            num_workers=num_workers,
            collate_fn=collate_fn)
    return iter(data_loader)


class FewRelDatasetWithSummary(data.Dataset):
    """
    FewRel Dataset
    """

    def __init__(self, name, encoder, N, K, Q, na_rate, root):
        self.root = root
        path = os.path.join(root, name + ".json")
        if not os.path.exists(path):
            print("[ERROR] Data file does not exist!")
            assert (0)
        self.json_data = json.load(open(path))
        self.classes = list(self.json_data.keys())
        self.N = N
        self.K = K
        self.Q = Q
        self.na_rate = na_rate
        self.encoder = encoder

    def __getraw__(self, item):
        word, pos1, pos2, mask = self.encoder.tokenize(item['tokens'],
                                                       item['h'][2][0],
                                                       item['t'][2][
                                                           0])  # mask的长度为句子编码长度，128，其中[:indexed_tokens] indexed_tokens=min(128,)
        return word, pos1, pos2, mask  # word是token的在glove词典中对应的id,pos1/pos2是每个token相对头尾实体的第一个索引的相对位置，mask[:indexed_token]为1

    def __getRawSmry__(self,item):
        word, pos1, pos2, mask, smry1, smry2 = self.encoder.tokenize(item['tokens'],
                                                       item['h'][2][0],
                                                       item['t'][2][0],item['h'][3],item['t'][3])  # mask的长度为句子编码长度，128，其中[:indexed_tokens] indexed_tokens=min(128,)
        return word, pos1, pos2, mask, smry1, smry2  # word是token的在glove词典中对应的id,pos1/pos2是每个token相对头尾实体的第一个索引的相对位置，mask[:indexed_token]为1

    def __additem__(self, d, word, pos1, pos2, mask):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)

    def __addSupportItem__(self, d, word, pos1, pos2, mask,smry1,smry2):
        d['word'].append(word)
        d['pos1'].append(pos1)
        d['pos2'].append(pos2)
        d['mask'].append(mask)
        d['smry1'].append(smry1)
        d['smry2'].append(smry2)


    def __getitem__(self, index):
        target_classes = random.sample(self.classes, self.N)
        support_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [],'smry1':[],'smry2':[]}
        query_set = {'word': [], 'pos1': [], 'pos2': [], 'mask': [],'smry1':[],'smry2':[]}
        query_label = []
        Q_na = int(self.na_rate * self.Q)
        na_classes = list(filter(lambda x: x not in target_classes,
                                 self.classes))

        for i, class_name in enumerate(target_classes):  # 从target_classes（N个）中，每个class中，随机选K+Q个关系类别
            indices = np.random.choice(
                list(range(len(self.json_data[class_name]))),
                self.K + self.Q, False)
            count = 0  # 统计样本个数
            for j in indices:  # 将word,pos1,pos2转为id
                # if count < self.K:
                #     word, pos1, pos2, mask, smry1, smry2 = self.__getRawSmry__(
                #         self.json_data[class_name][j])
                #     word = torch.tensor(word).long()
                #     pos1 = torch.tensor(pos1).long()
                #     pos2 = torch.tensor(pos2).long()
                #     mask = torch.tensor(mask).long()
                #     smry1= torch.tensor(smry1).long()
                #     smry2= torch.tensor(smry2).long()
                #     self.__addSupportItem__(support_set, word, pos1, pos2, mask,smry1,smry2)
                #
                #
                # else:
                #     word, pos1, pos2, mask = self.__getraw__(
                #         self.json_data[class_name][j])
                #     word = torch.tensor(word).long()
                #     pos1 = torch.tensor(pos1).long()
                #     pos2 = torch.tensor(pos2).long()
                #     mask = torch.tensor(mask).long()
                #     self.__additem__(query_set, word, pos1, pos2, mask)


                word, pos1, pos2, mask ,smry1,smry2= self.__getRawSmry__(
                    self.json_data[class_name][j])

                word = torch.tensor(word).long()
                pos1 = torch.tensor(pos1).long()
                pos2 = torch.tensor(pos2).long()
                mask = torch.tensor(mask).long()
                smry1 = torch.tensor(smry1).long()
                smry2 = torch.tensor(smry2).long()
                if count < self.K:  # 如果小于K个，继续补充support_set，大于构建query_set
                    self.__addSupportItem__(support_set, word, pos1, pos2, mask, smry1, smry2)
                else:
                    self.__addSupportItem__(query_set, word, pos1, pos2, mask, smry1, smry2)
                count += 1

            query_label += [i] * self.Q  # label用0-(N-1)的数字表示,每次增加Q个label

        # NA
        for j in range(Q_na):  # 若有na，则在K个query后再增加其他class的样本，label是N
            cur_class = np.random.choice(na_classes, 1, False)[0]
            index = np.random.choice(
                list(range(len(self.json_data[cur_class]))),
                1, False)[0]
            word, pos1, pos2, mask = self.__getraw__(
                self.json_data[cur_class][index])
            word = torch.tensor(word).long()
            pos1 = torch.tensor(pos1).long()
            pos2 = torch.tensor(pos2).long()
            mask = torch.tensor(mask).long()
            self.__additem__(query_set, word, pos1, pos2, mask)
        query_label += [self.N] * Q_na

        return support_set, query_set, query_label

    def __len__(self):
        return 1000000000


def collate_fn_with_summary(data):
    batch_support = {'word': [], 'pos1': [], 'pos2': [], 'mask': [],'smry1':[],'smry2':[]}
    batch_query = {'word': [], 'pos1': [], 'pos2': [], 'mask': [],'smry1':[],'smry2':[]}
    batch_label = []
    support_sets, query_sets, query_labels = zip(*data)
    for i in range(len(support_sets)):
        for k in support_sets[i]:
            batch_support[k] += support_sets[i][k]
        for k in query_sets[i]:
            batch_query[k] += query_sets[i][k]
        batch_label += query_labels[i]
    for k in batch_support:
        batch_support[k] = torch.stack(batch_support[k], 0)
    for k in batch_query:
        batch_query[k] = torch.stack(batch_query[k], 0)
    batch_label = torch.tensor(batch_label)
    return batch_support, batch_query, batch_label


def get_loader_with_summary(name, encoder, N, K, Q, batch_size,
               num_workers=8, collate_fn=collate_fn_with_summary, na_rate=0, root='./data'):
    dataset = FewRelDatasetWithSummary(name, encoder, N, K, Q, na_rate, root)
    data_loader = data.DataLoader(dataset=dataset,
                                  batch_size=batch_size,
                                  shuffle=False,
                                  pin_memory=True,
                                  num_workers=num_workers,
                                  collate_fn=collate_fn)
    return iter(data_loader)
