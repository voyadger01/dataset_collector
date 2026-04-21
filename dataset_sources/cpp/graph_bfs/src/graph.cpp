#include "graph.h"
#include <queue>
Graph::Graph(int v) : vertices(v), adj(v) {}
void Graph::addEdge(int u, int v) { adj[u].push_back(v); }
bool Graph::isConnected(int start) {
    std::vector<bool> visited(vertices, false);
    std::queue<int> q; q.push(start); visited[start] = true;
    while (!q.empty()) {
        int curr = q.front(); q.pop();
        for (int n : adj[curr]) if (!visited[n]) { visited[n] = true; q.push(n); }
    }
    for (bool v : visited) if (!v) return false;
    return true;
}
