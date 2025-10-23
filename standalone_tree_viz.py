#!/usr/bin/env python3
"""
Improved Standalone Minimax Tree Visualization for Queen's Gambit Declined
Creates CLEARER, more readable tree visualizations with better annotations
Optimized for readability per assignment requirements
"""

import chess
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle
import sys

def simple_evaluate(board):
    """Simple evaluation function for visualization"""
    if board.is_checkmate():
        return -10000 if board.turn else 10000
    if board.is_stalemate():
        return 0
    
    # Material count
    piece_values = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0
    }
    
    value = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            piece_value = piece_values[piece.piece_type]
            if piece.color == chess.WHITE:
                value += piece_value
            else:
                value -= piece_value
    
    # Small bonus for mobility
    value += len(list(board.legal_moves)) * 5
    
    return value if board.turn == chess.WHITE else -value

def create_minimax_visualization():
    """Create minimax tree from Queen's Gambit Declined"""
    
    # Set up Queen's Gambit Declined position
    board = chess.Board()
    moves = ['d2d4', 'd7d5', 'c2c4', 'e7e6']
    for move_uci in moves:
        board.push(chess.Move.from_uci(move_uci))
    
    print("Position: Queen's Gambit Declined")
    print("After: 1.d4 d5 2.c4 e6")
    print(board)
    print()
    
    # Create THREE separate figures for better clarity
    # Figure 1: Standard Minimax
    fig1 = plt.figure(figsize=(20, 14))
    ax1 = fig1.add_subplot(111)
    ax1.set_title("Minimax Tree - Queen's Gambit Declined\n(Depth 4 - Top 3 Moves per Node)", 
                  fontsize=18, fontweight='bold', pad=20)
    draw_minimax_tree(ax1, board, show_pruning=False, show_annotations=False)
    plt.tight_layout()
    plt.savefig("1_minimax_standard.png", dpi=150, bbox_inches='tight')
    print("✓ Saved: 1_minimax_standard.png")
    
    # Figure 2: With Alpha-Beta Pruning
    fig2 = plt.figure(figsize=(20, 14))
    ax2 = fig2.add_subplot(111)
    ax2.set_title("Alpha-Beta Pruning - Queen's Gambit Declined\n(Showing Pruned Branches with Red X)", 
                  fontsize=18, fontweight='bold', pad=20)
    draw_minimax_tree(ax2, board, show_pruning=True, show_annotations=False)
    plt.tight_layout()
    plt.savefig("2_alphabeta_pruning.png", dpi=150, bbox_inches='tight')
    print("✓ Saved: 2_alphabeta_pruning.png")
    
    # Figure 3: With Manual Annotation Guide
    fig3 = plt.figure(figsize=(20, 16))
    ax3 = fig3.add_subplot(111)
    ax3.set_title("Alpha-Beta Pruning with α/β Values\n(Ready for Manual Annotation)", 
                  fontsize=18, fontweight='bold', pad=20)
    draw_minimax_tree(ax3, board, show_pruning=True, show_annotations=True)
    plt.tight_layout()
    plt.savefig("3_alphabeta_annotated.png", dpi=150, bbox_inches='tight')
    print("✓ Saved: 3_alphabeta_annotated.png")
    
    plt.show()

def draw_minimax_tree(ax, board, show_pruning=False, show_annotations=False):
    """Draw a minimax tree with clear layout and readable labels"""
    G = nx.DiGraph()
    
    # Store additional node information
    node_info = {}
    pruning_info = {}
    alpha_beta_values = {}  # Store α/β at each node
    
    # Build tree structure
    node_counter = [0]
    
    def build_node(board, depth, parent_id=None, alpha=-float('inf'), beta=float('inf'), 
                   move_made=None, position_in_parent=0, total_siblings=1):
        """Recursively build tree nodes"""
        node_id = node_counter[0]
        node_counter[0] += 1
        
        # Store alpha/beta values
        alpha_beta_values[node_id] = {'alpha': alpha, 'beta': beta}
        
        # Evaluate position
        value = simple_evaluate(board)
        
        # Determine node type
        is_leaf = depth == 0 or board.is_game_over()
        is_max_node = depth % 2 == 0
        
        # Store node information
        node_info[node_id] = {
            'value': value if is_leaf else None,
            'final_value': None,
            'is_max': is_max_node,
            'is_leaf': is_leaf,
            'depth': depth,
            'alpha': alpha,
            'beta': beta,
            'position': position_in_parent,
            'total_siblings': total_siblings,
            'move_made': move_made
        }
        
        G.add_node(node_id)
        
        # Connect to parent
        if parent_id is not None:
            G.add_edge(parent_id, node_id, move=move_made)
        
        # Generate children if not leaf
        if not is_leaf and depth > 0:
            moves = list(board.legal_moves)
            
            # Score and select top 3 moves
            scored_moves = []
            for move in moves:
                score = 0
                # Prioritize captures
                if board.is_capture(move):
                    victim = board.piece_at(move.to_square)
                    if victim:
                        piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                                      chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
                        score += piece_values[victim.piece_type] * 100
                
                # Prioritize center moves
                if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5, chess.C5, chess.C4]:
                    score += 50
                
                # Check if move gives check
                board.push(move)
                if board.is_check():
                    score += 75
                board.pop()
                
                scored_moves.append((score, move))
            
            # Sort and take top 3 moves
            scored_moves.sort(key=lambda x: x[0], reverse=True)
            moves_to_show = [m for _, m in scored_moves[:3]]  # EXACTLY 3 moves
            
            # PRE-COMPUTE all move SANs before making any moves
            moves_san_list = []
            for move in moves_to_show:
                moves_san_list.append(board.san(move))
            
            children_values = []
            pruned_at_child = None
            
            for i, (move, move_san) in enumerate(zip(moves_to_show, moves_san_list)):
                board.push(move)
                
                # Check for pruning
                should_prune = False
                if show_pruning and i > 0:  # Can only prune after first child
                    if is_max_node and len(children_values) > 0:
                        current_max = max(children_values)
                        if current_max >= beta:
                            should_prune = True
                            pruned_at_child = i
                            pruning_info[node_id] = {
                                'reason': f'β-cutoff: max={current_max} ≥ β={beta}',
                                'at_child': i,
                                'alpha': alpha,
                                'beta': beta,
                                'value': current_max
                            }
                    elif not is_max_node and len(children_values) > 0:
                        current_min = min(children_values)
                        if current_min <= alpha:
                            should_prune = True
                            pruned_at_child = i
                            pruning_info[node_id] = {
                                'reason': f'α-cutoff: min={current_min} ≤ α={alpha}',
                                'at_child': i,
                                'alpha': alpha,
                                'beta': beta,
                                'value': current_min
                            }
                
                if should_prune:
                    board.pop()  # Pop the current move first
                    
                    # Add pruned node for current move
                    pruned_id = node_counter[0]
                    node_counter[0] += 1
                    node_info[pruned_id] = {
                        'is_pruned': True,
                        'is_leaf': True,
                        'depth': depth - 1,
                        'position': i,
                        'total_siblings': len(moves_to_show)
                    }
                    G.add_node(pruned_id)
                    G.add_edge(node_id, pruned_id, move=move_san, pruned=True)
                    
                    # Prune remaining children too
                    for j in range(i + 1, len(moves_to_show)):
                        pruned_id = node_counter[0]
                        node_counter[0] += 1
                        node_info[pruned_id] = {
                            'is_pruned': True,
                            'is_leaf': True,
                            'depth': depth - 1,
                            'position': j,
                            'total_siblings': len(moves_to_show)
                        }
                        G.add_node(pruned_id)
                        G.add_edge(node_id, pruned_id, move=moves_san_list[j], pruned=True)
                    break
                else:
                    # Recursively build child
                    child_id = build_node(board, depth - 1, node_id, alpha, beta, 
                                        move_san, i, len(moves_to_show))
                    child_value = node_info[child_id].get('final_value', node_info[child_id]['value'])
                    children_values.append(child_value)
                    
                    # Update alpha-beta
                    if is_max_node:
                        alpha = max(alpha, child_value)
                        alpha_beta_values[node_id]['alpha'] = alpha
                    else:
                        beta = min(beta, child_value)
                        alpha_beta_values[node_id]['beta'] = beta
                
                board.pop()
            
            # Set node's final value
            if children_values:
                if is_max_node:
                    node_info[node_id]['final_value'] = max(children_values)
                else:
                    node_info[node_id]['final_value'] = min(children_values)
        else:
            node_info[node_id]['final_value'] = value
        
        return node_id
    
    # Build the tree
    root = build_node(board, depth=4)
    
    # Calculate positions for better layout
    pos = calculate_tree_positions(G, node_info, root)
    
    # Draw edges
    for edge in G.edges():
        edge_data = G.edges[edge]
        start_pos = pos[edge[0]]
        end_pos = pos[edge[1]]
        
        if edge_data.get('pruned', False) and show_pruning:
            # Draw pruned edges
            ax.plot([start_pos[0], end_pos[0]], [start_pos[1], end_pos[1]], 
                   'r--', linewidth=2.5, alpha=0.6)
            # Add X mark
            mid_x = (start_pos[0] + end_pos[0]) / 2
            mid_y = (start_pos[1] + end_pos[1]) / 2
            ax.plot(mid_x, mid_y, 'rx', markersize=25, markeredgewidth=4)
        else:
            # Draw normal edges
            line_width = 3 if edge[0] == root and node_info[edge[1]].get('final_value') == node_info[root].get('final_value') else 1.5
            line_color = 'green' if line_width == 3 else 'black'
            ax.plot([start_pos[0], end_pos[0]], [start_pos[1], end_pos[1]], 
                   color=line_color, linewidth=line_width)
        
        # Add move labels with better positioning
        if 'move' in edge_data and not edge_data.get('pruned', False):
            mid_x = (start_pos[0] + end_pos[0]) / 2
            mid_y = (start_pos[1] + end_pos[1]) / 2
            
            # Add white background for readability
            bbox_props = dict(boxstyle="round,pad=0.4", facecolor="white", 
                            edgecolor="blue", alpha=0.95, linewidth=1.5)
            ax.text(mid_x, mid_y + 0.15, edge_data['move'], 
                   fontsize=13, ha='center', color='blue',
                   bbox=bbox_props, fontweight='bold')
    
    # Draw nodes
    for node in G.nodes():
        x, y = pos[node]
        info = node_info[node]
        
        if info.get('is_pruned', False):
            # Pruned node - red X
            ax.plot(x, y, 'rx', markersize=30, markeredgewidth=5)
            ax.text(x, y - 0.6, 'PRUNED', fontsize=11, ha='center', 
                   color='red', fontweight='bold')
        elif info.get('is_leaf', False):
            # Leaf node - green rectangle
            rect = FancyBboxPatch((x - 0.45, y - 0.3), 0.9, 0.6,
                                 boxstyle="round,pad=0.05",
                                 facecolor='lightgreen',
                                 edgecolor='darkgreen', linewidth=2.5)
            ax.add_patch(rect)
            # Show value
            value = info.get('final_value', info.get('value', '?'))
            ax.text(x, y, str(value), ha='center', va='center', 
                   fontsize=14, fontweight='bold')
        else:
            # Internal node
            is_max = info.get('is_max', False)
            color = 'lightblue' if is_max else 'lightcoral'
            circle = Circle((x, y), 0.4, facecolor=color, 
                          edgecolor='black', linewidth=2.5, zorder=3)
            ax.add_patch(circle)
            
            # Show value
            value = info.get('final_value', '?')
            ax.text(x, y, str(value), ha='center', va='center', 
                   fontsize=13, fontweight='bold', zorder=4)
            
            # Add MAX/MIN label
            label = 'MAX' if is_max else 'MIN'
            ax.text(x, y - 0.7, label, ha='center', va='top', 
                   fontsize=12, style='italic', fontweight='bold')
            
            # Add α/β annotations if requested
            if show_annotations and node in alpha_beta_values:
                ab = alpha_beta_values[node]
                alpha_str = f"α={ab['alpha']}" if ab['alpha'] != -float('inf') else "α=-∞"
                beta_str = f"β={ab['beta']}" if ab['beta'] != float('inf') else "β=+∞"
                
                # Show α/β values near node
                ax.text(x - 0.6, y + 0.5, alpha_str, ha='center', va='center',
                       fontsize=10, color='darkblue', fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))
                ax.text(x + 0.6, y + 0.5, beta_str, ha='center', va='center',
                       fontsize=10, color='darkred', fontweight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))
    
    # Add pruning annotations if requested
    if show_annotations and show_pruning:
        for node_id, prune_info in pruning_info.items():
            if node_id in pos:
                x, y = pos[node_id]
                # Add annotation explaining pruning
                ax.annotate(prune_info['reason'],
                           xy=(x, y), xytext=(x + 3, y - 1),
                           arrowprops=dict(arrowstyle='->', color='red', lw=2),
                           fontsize=11, color='red', fontweight='bold',
                           bbox=dict(boxstyle="round,pad=0.5", facecolor="white", 
                                   edgecolor='red', alpha=0.9, linewidth=2))
    
    # Add legend
    legend_elements = [
        mpatches.Patch(color='lightblue', label='MAX Node (White to move)'),
        mpatches.Patch(color='lightcoral', label='MIN Node (Black to move)'),
        mpatches.Patch(color='lightgreen', label='Leaf Node (Evaluation)'),
    ]
    
    if show_pruning:
        legend_elements.extend([
            mpatches.Patch(color='red', label='Pruned Branch'),
            mpatches.Patch(color='green', label='Best Move Path')
        ])
    
    ax.legend(handles=legend_elements, loc='upper right', fontsize=12)
    
    # Set axis limits and styling
    ax.set_xlim(-8, 8)
    ax.set_ylim(-11, 1.5)
    ax.axis('off')
    
    # Add position info
    ax.text(-7.5, 1, "Position: Queen's Gambit Declined\n1.d4 d5 2.c4 e6\nWhite to move", 
           fontsize=13, bbox=dict(boxstyle="round,pad=0.5", facecolor="yellow", alpha=0.4),
           fontweight='bold')
    
    # Add final decision
    if node_info[root].get('final_value'):
        best_move = None
        for child in G.successors(root):
            if node_info[child].get('final_value') == node_info[root]['final_value']:
                best_move = G.edges[(root, child)]['move']
                break
        
        if best_move:
            ax.text(0, 1, f"Best Move: {best_move} (Value: {node_info[root]['final_value']})",
                   fontsize=16, ha='center', fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.6", facecolor="lightgreen", 
                           edgecolor='darkgreen', alpha=0.9, linewidth=2))
    
    # Add explanation box if showing annotations
    if show_annotations and show_pruning:
        explanation = (
            "Alpha-Beta Pruning Rules:\n"
            "• At MAX node: Prune when max ≥ β\n"
            "  (MIN parent won't choose this path)\n"
            "• At MIN node: Prune when min ≤ α\n"
            "  (MAX parent won't choose this path)\n"
            "Green = Best path selected"
        )
        
        ax.text(5.5, -9, explanation, fontsize=11,
               bbox=dict(boxstyle="round,pad=0.6", facecolor="lightcyan", 
                       edgecolor='blue', alpha=0.8, linewidth=2),
               verticalalignment='top', fontweight='bold')

def calculate_tree_positions(G, node_info, root):
    """Calculate positions for tree nodes with better spacing"""
    pos = {}
    
    # Build level structure
    levels = {}
    queue = [(root, 0)]
    visited = set()
    
    while queue:
        node, level = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        
        if level not in levels:
            levels[level] = []
        levels[level].append(node)
        
        for child in G.successors(node):
            queue.append((child, level + 1))
    
    # Position nodes with proper spacing
    y_spacing = -2.5
    
    for level, nodes in levels.items():
        y = level * y_spacing
        
        # Calculate x positions with more space
        if len(nodes) == 1:
            pos[nodes[0]] = (0, y)
        else:
            # Wider spacing at lower levels
            width = min(15, 3 + level * 3)
            x_positions = []
            for i in range(len(nodes)):
                x = -width/2 + (i * width)/(len(nodes) - 1)
                x_positions.append(x)
            
            for node, x in zip(nodes, x_positions):
                pos[node] = (x, y)
    
    return pos

def main():
    """Main function"""
    print("=" * 60)
    print("Minimax Tree Visualization Generator")
    print("Queen's Gambit Declined Opening")
    print("=" * 60)
    
    create_minimax_visualization()
    
    print("\n✅ Visualization complete!")
    print("\nGenerated files:")
    print("  1. 1_minimax_standard.png - Standard minimax tree")
    print("  2. 2_alphabeta_pruning.png - With pruned branches marked")
    print("  3. 3_alphabeta_annotated.png - With α/β values for manual annotation")
    print("\nNext steps:")
    print("  • Add these images to your README")
    print("  • Optionally print image 3 and manually annotate pruning decisions")

if __name__ == "__main__":
    main()