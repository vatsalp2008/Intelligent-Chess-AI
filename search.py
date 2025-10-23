import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np

class MinimaxTree:
    def __init__(self):
        self.G = nx.DiGraph()
        self.node_values = {}
        self.node_types = {}  # 'MAX' or 'MIN'
        self.leaf_values = {}
        self.pruned_edges = set()
        self.chosen_path = []
        
    def create_tree(self):
        """Create the tree structure from the image"""
        # Level 0 (root - MAX)
        self.G.add_node('A', level=0)
        self.node_types['A'] = 'MAX'
        
        # Level 1 (MIN)
        self.G.add_edge('A', 'B', label='L')
        self.G.add_edge('A', 'C', label='R')
        self.node_types['B'] = 'MIN'
        self.node_types['C'] = 'MIN'
        
        # Level 2 (MAX)
        self.G.add_edge('B', 'D', label='L')
        self.G.add_edge('B', 'E', label='R')
        self.G.add_edge('C', 'F', label='L')
        self.G.add_edge('C', 'G', label='R')
        for node in ['D', 'E', 'F', 'G']:
            self.node_types[node] = 'MAX'
        
        # Level 3 (Leaf nodes)
        # From D
        self.G.add_edge('D', 'L1', label='L')
        self.G.add_edge('D', 'L2', label='R')
        # From E
        self.G.add_edge('E', 'L3', label='L')
        self.G.add_edge('E', 'L4', label='R')
        # From F
        self.G.add_edge('F', 'L5', label='L')
        self.G.add_edge('F', 'L6', label='R')
        # From G
        self.G.add_edge('G', 'L7', label='L')
        self.G.add_edge('G', 'L8', label='R')
        
        # Set leaf values
        leaf_vals = [3, 5, 6, 9, 1, 2, 0, -1]
        leaf_nodes = ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'L8']
        
        for node, val in zip(leaf_nodes, leaf_vals):
            self.leaf_values[node] = val
            self.node_values[node] = val
            self.node_types[node] = 'LEAF'
    
    def minimax(self, node='A'):
        """Implement minimax algorithm"""
        if node in self.leaf_values:
            return self.leaf_values[node]
        
        children = list(self.G.successors(node))
        
        if self.node_types[node] == 'MAX':
            max_val = float('-inf')
            best_child = None
            for child in children:
                val = self.minimax(child)
                if val > max_val:
                    max_val = val
                    best_child = child
            self.node_values[node] = max_val
            
            # Track chosen path
            if node == 'A' and best_child:
                self.trace_chosen_path('A', best_child)
            
            return max_val
        else:  # MIN node
            min_val = float('inf')
            for child in children:
                val = self.minimax(child)
                min_val = min(min_val, val)
            self.node_values[node] = min_val
            return min_val
    
    def trace_chosen_path(self, start, next_node):
        """Trace the chosen path from root to leaf"""
        self.chosen_path = []
        
        def dfs(node):
            if node in self.leaf_values:
                return True
            
            children = list(self.G.successors(node))
            if not children:
                return False
            
            if self.node_types[node] == 'MAX':
                # Choose max child
                best_val = float('-inf')
                best_child = None
                for child in children:
                    if self.node_values[child] > best_val:
                        best_val = self.node_values[child]
                        best_child = child
            else:  # MIN
                # Choose min child
                best_val = float('inf')
                best_child = None
                for child in children:
                    if self.node_values[child] < best_val:
                        best_val = self.node_values[child]
                        best_child = child
            
            if best_child:
                self.chosen_path.append((node, best_child))
                return dfs(best_child)
            return False
        
        self.chosen_path.append((start, next_node))
        dfs(next_node)
    
    def alpha_beta(self, node='A', alpha=float('-inf'), beta=float('inf'), parent=None):
        """Implement alpha-beta pruning"""
        if node in self.leaf_values:
            return self.leaf_values[node]
        
        children = list(self.G.successors(node))
        
        if self.node_types[node] == 'MAX':
            max_val = float('-inf')
            for i, child in enumerate(children):
                # Check if we should prune remaining children
                if i > 0 and max_val >= beta:
                    # Prune remaining children
                    for j in range(i, len(children)):
                        self.pruned_edges.add((node, children[j]))
                    break
                    
                val = self.alpha_beta(child, alpha, beta, node)
                max_val = max(max_val, val)
                alpha = max(alpha, max_val)
                
            self.node_values[node] = max_val
            return max_val
        else:  # MIN node
            min_val = float('inf')
            for i, child in enumerate(children):
                # Check if we should prune remaining children
                if i > 0 and min_val <= alpha:
                    # Prune remaining children
                    for j in range(i, len(children)):
                        self.pruned_edges.add((node, children[j]))
                    break
                    
                val = self.alpha_beta(child, alpha, beta, node)
                min_val = min(min_val, val)
                beta = min(beta, min_val)
                
            self.node_values[node] = min_val
            return min_val
    
    def visualize(self, title="Search Tree", show_values=False, show_chosen=False, show_pruned=False):
        """Visualize the tree"""
        plt.figure(figsize=(14, 8))
        
        # Calculate positions using hierarchical layout
        pos = self._calculate_positions()
        
        # Draw edges
        for edge in self.G.edges():
            if show_pruned and edge in self.pruned_edges:
                # Draw pruned edges with red X
                nx.draw_networkx_edges(self.G, pos, [(edge[0], edge[1])], 
                                      edge_color='red', style='dashed', width=2, alpha=0.5)
                # Add X mark
                x1, y1 = pos[edge[0]]
                x2, y2 = pos[edge[1]]
                plt.plot([(x1+x2)/2], [(y1+y2)/2], 'rx', markersize=15, markeredgewidth=3)
            elif show_chosen and edge in self.chosen_path:
                nx.draw_networkx_edges(self.G, pos, [(edge[0], edge[1])], 
                                      edge_color='green', width=3)
            else:
                nx.draw_networkx_edges(self.G, pos, [(edge[0], edge[1])], 
                                      edge_color='black', width=1)
        
        # Draw edge labels
        edge_labels = nx.get_edge_attributes(self.G, 'label')
        nx.draw_networkx_edge_labels(self.G, pos, edge_labels, font_size=10)
        
        # Draw nodes
        for node in self.G.nodes():
            x, y = pos[node]
            
            if node in self.leaf_values:
                # Leaf nodes - green squares
                rect = FancyBboxPatch((x-0.03, y-0.03), 0.06, 0.06,
                                     boxstyle="round,pad=0.01",
                                     facecolor='lightgreen',
                                     edgecolor='black', linewidth=2)
                plt.gca().add_patch(rect)
                
                # Show leaf value
                plt.text(x, y, str(self.leaf_values[node]), 
                        ha='center', va='center', fontsize=12, fontweight='bold')
            else:
                # Internal nodes - circles
                circle = plt.Circle((x, y), 0.03, color='white', 
                                   edgecolor='black', linewidth=2, zorder=3)
                plt.gca().add_patch(circle)
                
                # Show node label
                plt.text(x, y, node, ha='center', va='center', 
                        fontsize=11, fontweight='bold', zorder=4)
                
                # Show computed value if available
                if show_values and node in self.node_values:
                    plt.text(x, y+0.08, str(self.node_values[node]), 
                            ha='center', va='center', fontsize=10, 
                            color='red', fontweight='bold')
        
        # Add level labels
        plt.text(-0.15, 0, 'MAX', fontsize=12, fontweight='bold')
        plt.text(-0.15, -0.33, 'MIN', fontsize=12, fontweight='bold')
        plt.text(-0.15, -0.66, 'MAX', fontsize=12, fontweight='bold')
        
        plt.title(title, fontsize=14, fontweight='bold')
        plt.axis('equal')
        plt.axis('off')
        plt.tight_layout()
        plt.show()
    
    def _calculate_positions(self):
        """Calculate node positions for visualization"""
        pos = {}
        
        # Level 0
        pos['A'] = (0.5, 0)
        
        # Level 1
        pos['B'] = (0.25, -0.33)
        pos['C'] = (0.75, -0.33)
        
        # Level 2
        pos['D'] = (0.125, -0.66)
        pos['E'] = (0.375, -0.66)
        pos['F'] = (0.625, -0.66)
        pos['G'] = (0.875, -0.66)
        
        # Level 3 (leaves)
        leaf_x = np.linspace(0.05, 0.95, 8)
        for i, node in enumerate(['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'L8']):
            pos[node] = (leaf_x[i], -1)
        
        return pos

# Execute the implementation
def main():
    # Step 1 & 2: Create and visualize the initial tree
    print("Step 1 & 2: Creating and visualizing the initial search tree")
    tree = MinimaxTree()
    tree.create_tree()
    tree.visualize(title="Initial Search Tree (Step 1 & 2)")
    
    # Step 3 & 4: Run minimax and show the chosen path
    print("\nStep 3 & 4: Running Minimax algorithm")
    tree_minimax = MinimaxTree()
    tree_minimax.create_tree()
    result = tree_minimax.minimax()
    print(f"Minimax value at root: {result}")
    print(f"Node values after minimax: {tree_minimax.node_values}")
    tree_minimax.visualize(title="Minimax Tree with Values and Chosen Path (Step 3 & 4)", 
                           show_values=True, show_chosen=True)
    
    # Step 5 & 6: Run alpha-beta pruning and show pruned edges
    print("\nStep 5 & 6: Running Alpha-Beta Pruning")
    tree_ab = MinimaxTree()
    tree_ab.create_tree()
    result_ab = tree_ab.alpha_beta()
    print(f"Alpha-Beta result at root: {result_ab}")
    print(f"Pruned edges: {tree_ab.pruned_edges}")
    tree_ab.visualize(title="Alpha-Beta Pruning with Pruned Edges (Step 5 & 6)", 
                     show_values=True, show_pruned=True)

if __name__ == "__main__":
    main()