[![Open in Visual Studio Code](https://classroom.github.com/assets/open-in-vscode-2e0aaae1b6195c2367325f4f02e2d04e9abb55f0b24a779b69b11b9e10269abc.svg)](https://classroom.github.com/online_ide?assignment_repo_id=21503435&assignment_repo_type=AssignmentRepo)
# ChessGPT 🤖♟️🏆

For this assignment, you will be building a chess-playing agent that relies on an LLM to determine its moves. Instead of implementing Minimax or Alpha-Beta Pruning, you will explore how different LLMs respond to chess prompts and discover ways to refine them.

---

## 🔧🛠️ Setting Up the LLM Chessbot

You must complete this section before moving on to the next of the homework.

1. Install and set up [Ollama](https://ollama.com/) to run different LLMs locally. Follow their installation guide for your device. You may also need to run `pip install ollama` afterwards.
2. Select at least two different LLMs available in Ollama to compare performance (e.g., `llama`, `mistral`, `gemma`) and download them using the `ollama run` command. Keep in mind that larger models need more memory to run.
3. Get [examplellm.py](examplellm.py) to run successfully with your chosen models.
4. Create a new chess bot based off your earlier bot, but alter it to interact with Ollama when deciding on moves instead of using search and evaluation functions. Have it use the same api calls as [examplellm.py](examplellm.py) when interacting with Ollama.

Do **not**  make API calls to ChatGPT or other online LLM tools. This is all being done locally with Ollama. It is also a good idea to terminate the Ollama application when you are not using it.

---

## 🔄 Experimentation and Refinement


### 🏗️👷🏽‍♀️🧑🏼‍🏭🐞 Prompt Engineering and Debugging

1. Experiment with different prompt structures to find one that consistently produces valid chess moves given either the current board position, the bot's last move, a history of all moves, or some other strategy.
   - You can try telling the LLM something along the lines of: "I just moved the pawn on e2 to e4, what is your move?"
   - Consider telling it what its valid moves are.
   - Figure out a way to get the output that you want in a format that you'll be able to parse.
   - Some models are incredibly verbose and will not follow your intructions no matter how hard you try. Switch to a different model when this happens.
2. Test the bot and log cases where the LLM struggles or hallucinates. This means you will need to programmatically log outputs to a file for every response in a game in order to identify when it had to retry and what it did.
3. Develop a method to recover from invalid moves, such as:
   - Trying again.
   - Re-prompting with a different kind of board representation.
   - Adjusting prompt wording to explain what went wrong and what can be done.
4. Document the final set of prompts and re-prompts that you settled on for each model below.
5. Play against random and mate-in-one bots from earlier to evaluate performance.

### LLMs - Fill in the following

#### LLM 1: llama3.2

**Model:** llama3.2 (via Ollama)

**Final Prompt Strategy:**

After testing 5 different prompt approaches, I found that simplified prompts worked best (85.7% success rate vs 26% for complex strategic prompts). My final prompt is:
```python
prompt = f"""Pick ONE move from this list: {legal_moves_str}

Board:
{board}

Reply with just the move (like e2e4)."""
```

**Key Design Decisions:**
- Limit legal moves to first 15 (prevents overwhelming the LLM)
- Use minimal instructions - simpler is better
- Include example format (e2e4)
- No strategic guidance (actually confused the LLM)

**Recovery Strategy:**
- Try up to 3 times with same prompt
- Parse response flexibly (look for move anywhere in output, try first token)
- Fallback to random move if all attempts fail

**Performance:**
- Valid move rate: ~45% 
- First attempt success: ~20%
- Final tournament: 1 win out of 24 games (4.2%)

---

#### LLM 2: mistral

**Model:** mistral (via Ollama)

**Prompt Strategy:**

Used the same simplified approach as llama3.2, plus tested recovery strategies:
1. Standard prompt with UCI examples
2. Feedback-based re-prompting (explaining errors)
3. Numbered list selection
4. Simplified prompt

**Performance:**
- Early testing showed 0 wins
- Performed worse than llama3.2 in head-to-head matches
- Recovery strategy analysis: simplified (85.7%) and numbered (69.6%) worked best

**Conclusion:**
Mistral was less effective for chess than llama3.2, so I focused optimization efforts on llama3.2.
---

## 💭 Reflection

**1. What was your strategy for designing your prompts? What changes did you make to improve its reliability? What challenges did you face in getting the LLM(s) to output valid chess moves?**

My initial strategy was to give the LLM strategic chess guidance (control center, develop pieces, etc.), thinking more context would help. I tested 5 different prompt versions and discovered the opposite was true - simpler prompts worked dramatically better. The simplified prompt ("Pick ONE move from this list") achieved 85.7% success rate while the strategic guidance prompt only got 26%.

The biggest challenge was the format mismatch between what LLMs naturally output (algebraic notation like "e4") versus what the chess engine needs (UCI format like "e2e4"). Even with explicit examples, the LLM frequently reverted to algebraic notation. I improved this by:
- Adding clear UCI format examples (e2e4, g1f3, not e4 or Nf3)
- Parsing responses more flexibly (searching for valid moves anywhere in output)
- Implementing retry logic with up to 3 attempts

This improved valid move rate from 30.1% to 45.4%, though still far from perfect.

**2. How did different models compare in move selection? Was one more consistent or strategic than other?**

llama3.2 significantly outperformed mistral. In early head-to-head testing, llama3.2 won both games against mistral. llama3.2 was better at following the simplified prompt format and made more sensible moves overall. Mistral struggled more with UCI notation and had a 0% win rate in testing, so I focused my optimization efforts entirely on llama3.2.

**3. What approaches did you take when the LLM generated invalid or nonsensical moves? How effective were these approaches?**

I implemented a multi-strategy recovery system:
1. Standard retry (3 attempts with same prompt)
2. Feedback-based re-prompting (explaining what went wrong)
3. Numbered list selection (explicit move options)
4. Simplified minimal prompt
5. Random fallback if all fail

Analysis showed that simplified and numbered approaches were most effective (85.7% and 69.6% success rates respectively), while feedback-based recovery didn't help much (25.8%). The key insight was that simpler prompts work better than trying to explain errors - LLMs do better when given less to think about.

I also improved parsing to handle common mistakes like dashes (e2-e4) and look for UCI patterns anywhere in the response using regex.

**4. How did your LLM-based bot perform compared to the random_bot, mate_in_one bot, and your prior minimax bot in your own testing tournaments? What factors influenced these results?**

Final tournament results (24 games each):
- Minimax (Knightmare): 75.0% win rate (18 wins)
- Random Bot: 60.4% win rate (14.5 wins)
- Mate-in-One Bot: 60.4% win rate (14.5 wins)
- LLM Bot: 4.2% win rate (1 win)

The LLM bot performed significantly worse than all opponents. Key factors:

*Why it lost:* Even with ~45% valid move rate, 55% of moves were random fallbacks, not actual LLM decisions. When the LLM did generate valid moves, they often lacked strategic depth - it would make legal but poor moves like moving the same knight repeatedly (Nh6, Ng8, Nh6, Ng8).

*Why minimax dominated:* Minimax evaluates positions 4 moves deep with alpha-beta pruning, giving it real strategic planning. It found checkmates and executed coherent strategies.

*The one win:* The LLM bot did deliver a checkmate against Mate-in-One bot once, showing it can occasionally find tactics, but this was rare.

**5. If you had more time, what further refinements would you make to your approach?**

- Maybe fine-tune a small model specifically on chess games in UCI format so it learns the notation
- Try showing it the board as an image instead of text (vision models might be better)
- Hybrid approach - use LLM for opening strategy, switch to minimax for middle/endgame
- Chain of thought - make it explain its reasoning first, might help it think more strategically
- Test if asking it to evaluate multiple moves and pick the best works better than just picking one
- Look into models specifically trained for games/logic tasks

Honestly the main issue is LLMs just aren't built for this kind of structured output. They're designed for natural language, not chess notation.

**6. (Optional) What changes would you want me to make to this homework if I were to give it again?**


🎉 Happy coding, and may the best LLM chessbot win! ♜🏆

