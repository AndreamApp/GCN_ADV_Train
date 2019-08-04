from __future__ import division
from __future__ import print_function

import time
import tensorflow as tf
import scipy.sparse as sp
import copy
import numpy as np
import matplotlib.pyplot as plt


from utils import parse_index_file, sample_mask, load_data, sparse_to_tuple, preprocess_features, normalize_adj, preprocess_adj, construct_feed_dict, bisection, filter_potential_singletons
from models import GCN




class PGDAttack:
  def __init__(self, sess, model, features, epsilon, k, mu, ori_adj):
    self.sess = sess
    self.model = model
    self.features = features
    self.eps = epsilon
    self.ori_adj = ori_adj
    self.total_edges = np.sum(self.ori_adj)/2
    self.n_node = self.ori_adj.shape[-1] 
    self.mu = mu
    self.xi = 1e-5
    

  def evaluate(self, support, labels, mask):
    t_test = time.time()
    feed_dict_val = construct_feed_dict(self.features, support, labels, mask, self.model.placeholders)
    feed_dict_val.update({self.model.placeholders['support'][i]: support[i] for i in range(len(support))})
    outs_val = self.sess.run([self.model.attack_loss, self.model.accuracy], feed_dict=feed_dict_val)
    return outs_val[0], outs_val[1], (time.time() - t_test)

  def perturb(self, feed_dict, discrete, y_test, test_mask, k, eps= None):
      
    if eps: self.eps = eps
    for epoch in range(k):
    
        t = time.time()
        feed_dict.update({self.model.placeholders['mu']: self.mu/np.sqrt(epoch+1)})
        
        # s \in [0,1]
        a,support,modified_adj = self.sess.run([self.model.a,self.model.placeholders['support'],self.model.modified_A], feed_dict=feed_dict)
        modified_adj = np.array(modified_adj[0])
        upper_S_update = bisection(a,self.eps,self.xi)
        
        feed_dict.update({self.model.placeholders['s'][i]: upper_S_update[i] for i in range(len(upper_S_update))})
        
        if discrete:
            upper_S_update_tmp = upper_S_update[:]
            if epoch == k-1:
                for  i in range(1):
                    print('last round, perturb edges by probabilities!')
                    randm = np.random.uniform(size=(self.n_node,self.n_node))
                    upper_S_update = np.where(upper_S_update_tmp>randm,1,0)
                    feed_dict.update({self.model.placeholders['s'][i]: upper_S_update[i] for i in range(len(upper_S_update))})
                    a,support_d,modified_adj_d = self.sess.run([self.model.a,self.model.placeholders['support'],self.model.modified_A], feed_dict=feed_dict)
                    modified_adj_d = np.array(modified_adj_d[0])
                    #plt.plot(np.sort(upper_S_update[np.nonzero(upper_S_update)]))
                    cost, acc, duration = self.evaluate(support_d, y_test, test_mask)
                    print("Epoch:", '%04d' % (epoch + 1), "loss on the given data =", "{:.5f}".format(cost),
                      "acc on the given data =", "{:.5f}".format(acc), "time=", "{:.5f}".format(time.time() - t))
                    print('random end!')
                break
        cost, acc, duration = self.evaluate(support, y_test, test_mask)
        
        # Print results
        print("Step:", '%04d' % (epoch + 1), "val_loss=", "{:.5f}".format(cost),
              "val_acc=", "{:.5f}".format(acc), "time=", "{:.5f}".format(time.time() - t))
        
      # if epoch > FLAGS.early_stopping and cost_val[-1] > np.mean(cost_val[-(FLAGS.early_stopping+1):-1]):
      #     print("Early stopping...")
      #     break
    if discrete:
        print("perturb ratio", np.count_nonzero(upper_S_update[0])/self.total_edges)
    else:
        print("perturb ratio (count by L1)", np.sum(upper_S_update[0])/self.total_edges)
    
    print("attack Finished!")

    #return modified_adj_d,feed_dict if discrete else modified_adj,feed_dict
    return support_d if discrete else support
