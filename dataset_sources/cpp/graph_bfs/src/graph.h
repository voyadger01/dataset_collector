#ifndef GRAPH_H
#define GRAPH_H
#include <vector>
class Graph {
public:
    Graph(int v);
    void addEdge(int u, int v);
    bool isConnected(int start);
private:
    int vertices;
    std::vector<std::vector<int>> adj;
};
#endif
