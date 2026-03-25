You are builting a complete LaTeX answer sheet for an algorithms homework. Provide a full LaTeX source code for the answer sheet, including a summary of each problem, but **leave all solutions as TODO** for the student to fill in.

Output requirements:
- Return exactly one fenced code block labeled `latex`.
- Do not write anything outside that code block.
- The generated LaTeX should be suitable for `main.tex` and should compile once the provided preamble is injected.

Writing requirements:
- Use a clean answer-sheet style: `\maketitle`, then `\problem{...}` for each problem.
- You are expected to reconstruct the pdf assignment in LaTeX for each problem precisely. After each problem, a "Solution: TODO" should be inserted for the student to fill in.
- If you see issues where the assignment seems incomplete, or strange, assume it as issues with PDF to Text conversion. In the TODO for this question, include a note to the student to check the original PDF for any missing information or formatting issues, in the form of latex comments. Apart from this nothing should exist alongside the TODO.
- If the assignment asks for personal information that the model cannot know (such as time spent, collaborators, or self-rated difficulty), do not fabricate it. Instead include an explicit placeholder for the student to fill in manually.
- Closely follow the format defined in `example.tex`. Do not add additional sections in your output.

Preamble file path (reference only):
{{ preamble_path }}

Preamble content (reference only):
```
{{ preamble_content }}
```

Assignment PDF filename: {{ assignment_pdf_name }}

Assignment material:
{{ assignment_material }}

Example tex output (alter to match the assignment):
```
{{ example_tex_content }}
```