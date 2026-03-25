You are builting a complete LaTeX answer sheet for an algorithms homework. Provide a full LaTeX source code for the answer sheet, including a summary of each problem, but **leave all solutions as TODO** for the student to fill in.

Output requirements:
- Return exactly one fenced code block labeled `latex`.
- Do not write anything outside that code block.
- Do not include `\documentclass`.
- Do not paste the preamble verbatim unless you need to add extra packages or macros beyond it.
- The generated LaTeX should be suitable for `main.tex` and should compile once the provided preamble is injected.

Writing requirements:
- Use a clean answer-sheet style: `\maketitle`, then `\problem{...}` for each problem.
- For algorithm-design questions, explicitly include: the algorithm idea, why it is correct, and its asymptotic running time.
- For long problems, do not restate the entire problem statement, but you are expected to summarize the problem before each solution section which acts as a reminder of what the problem is about.
- If the assignment asks for personal information that the model cannot know (such as time spent, collaborators, or self-rated difficulty), do not fabricate it. Instead include an explicit placeholder for the student to fill in manually.

Preamble file path (reference only):
{{ preamble_path }}

Preamble content (reference only):
```
{{ preamble_content }}
```

Assignment PDF filename: {{ assignment_pdf_name }}

Assignment material:
{{ assignment_material }}
