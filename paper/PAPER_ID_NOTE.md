# Paper ID Replacement Note

SOSP 2026 requires double-blind submissions. The title block on the first page should use the submission-system paper ID instead of author names and affiliations.

Current placeholder (already in the blind PDF source):

- File: `paper/kernelscript-paper.tex`
- Title-block: `\author{Paper ID: TBD}` and `\renewcommand{\shortauthors}{Paper ID: TBD}`
- Real author/affiliation lines are kept only as LaTeX comments for camera-ready restore

Before submission:

1. Get the assigned paper ID from the SOSP/eBPF workshop submission system.
2. Replace `TBD` in `\author{Paper ID: TBD}` (and shortauthors) with the real paper ID.
3. Keep author names, affiliations, acknowledgments, and other identifying metadata out of the submission PDF.
4. After acceptance, restore the commented camera-ready author block for the final version.

Relevant source links:

- SOSP 2026 CFP: https://sigops.org/s/conferences/sosp/2026/cfp.html
- eBPF Workshop 2026 CFP: https://ebpf.github.io/2026/cfp.html
