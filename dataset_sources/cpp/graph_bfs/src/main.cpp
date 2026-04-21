#include <iostream>
#include "graph.h"
int main() {
    Graph g(4);
    g.addEdge(0,1); g.addEdge(1,2); g.addEdge(2,0); g.addEdge(3,3);
    std::cout << "Connected: " << (g.isConnected(0) ? "Yes" : "No") << '\n';
    return 0;
}
