# Labelled photo set for `--eval-photos`

Photos of handwritten working are personal data, so none are committed. Build your own set in 30 minutes:

1. Pick the four photo questions: Q21 (2/3 + 1/6), Q22 (3/4 + 1/4), Q37 (3/5 divided by 3/10), Q41 (2 cakes x 3/4 cup).
2. Five people each write all four on plain or ruled paper: some correct, some with a deliberate misconception from `data/fractions.json` (for example adding the denominators in Q22). Vary pens and handwriting.
3. Photograph each with a phone in normal light, name them `p01.jpg` to `p20.jpg`, and put them in this folder.
4. Copy `labels.example.jsonl` to `labels.jsonl` and write one line per photo:

   ```json
   {"file": "p01.jpg", "question_id": "Q22", "label_correct": false, "label_error_step": 2, "label_tag": "add_denominators"}
   ```

   `label_error_step` is the 1-based line number of the first wrong step as written; use `null` when the working is correct.
5. Run `python main.py --eval-photos data/eval_photo` with `GEMINI_API_KEY` set.

The script prints right/wrong accuracy, misconception accuracy and wrong-step accuracy, and lists any photo the model could not read.
