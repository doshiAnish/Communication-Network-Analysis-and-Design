import networkx as nx
import numpy as np


def exact_num_trees(graph):
    """
    Computes the number of spanning trees that can be generated for the given
    graph. The graph needs to be connected and undirected.
    See https://en.wikipedia.org/wiki/Spanning_tree#In_arbitrary_graphs
    and also https://en.wikipedia.org/wiki/Kirchhoff%27s_theorem.

    Have run this on the Chinese network with 54 nodes and 102 edges to get
    the number of trees = 1.0e23
    """
    adj_g = nx.adjacency_matrix(graph, weight=None).todense()  # Needed due to change in NetworkX
    l_g = -1*adj_g
    for i, n in enumerate(graph.nodes()):
        l_g[i, i] = nx.degree(graph, n)
    # for the matrix by deleting one row and column from l_g
    l_gm = l_g[0:-1, 0:-1]
    return np.linalg.det(l_gm)







