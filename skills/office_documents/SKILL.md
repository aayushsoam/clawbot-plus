---
name: Office Document Generator
description: This skill teaches you how to PROPERLY create or edit binary document formats like PowerPoint (.pptx), Excel (.xlsx), and Word (.docx).
tags: [powerpoint, excel, word, pptx, xlsx, docx, documents]
---

# Office Document Generator Skill

You must **NEVER** use the `create_file` action or `echo` commands to create `.pptx`, `.xlsx`, or `.docx` files. Those are binary formats. If you try to write text to them, they will become corrupted!

Instead, when the user asks you to create a presentation, spreadsheet, or document, you must ALWAYS use the `run_code` action to execute a Python script that relies on native libraries.

## How to Create a PowerPoint (.pptx)
1. Use `run_code` exactly like this string:
```python
import subprocess
try:
    import pptx
except ImportError:
    subprocess.run(["pip", "install", "python-pptx", "--user"], check=True)
    import pptx

from pptx import Presentation
from pptx.util import Inches, Pt

prs = Presentation()
# Title Slide
slide = prs.slides.add_slide(prs.slide_layouts[0])
slide.shapes.title.text = "Project Title"
slide.placeholders[1].text = "Subtitle goes here"

# Content Slide
slide = prs.slides.add_slide(prs.slide_layouts[1])
slide.shapes.title.text = "Features"
tf = slide.shapes.placeholders[1].text_frame
tf.text = "First feature"
tf.add_paragraph().text = "Second feature"

prs.save("Presentation.pptx")
print("Successfully created Presentation.pptx!")
```

## How to Create an Excel File (.xlsx)
Use `pandas` and `openpyxl`.
```python
import subprocess
try:
    import pandas as pd
except ImportError:
    subprocess.run(["pip", "install", "pandas", "openpyxl", "--user"], check=True)
    import pandas as pd

import os
# Create dataframe
df = pd.DataFrame({
    "Name": ["Alice", "Bob"],
    "Score": [90, 85]
})
df.to_excel("Report.xlsx", index=False)
print("Successfully created Report.xlsx!")
```

## How to Create a Word Document (.docx)
Use `python-docx`.
```python
import subprocess
try:
    import docx
except ImportError:
    subprocess.run(["pip", "install", "python-docx", "--user"], check=True)
    import docx

doc = docx.Document()
doc.add_heading('Document Title', 0)
doc.add_paragraph('This is a paragraph in the docx file.')
doc.save("Document.docx")
print("Successfully created Document.docx!")
```

**CRITICAL RULE:** Always wrap the library import in a `try...except ImportError` block that runs `pip install` internally, so the code never fails if the PC doesn't have the library!
