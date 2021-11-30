import os
import tempfile
from typing import IO


def get_pdf_full_text(pdf_file_like: IO) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file_name = f"{tmpdir}/tmp.pdf"
        with open(tmp_file_name, mode="wb") as pdf_file:
            pdf_file.write(pdf_file_like.read())

        pdf_to_text_cmd = f"pdftotext -nopgbrk -layout '{tmp_file_name}' -"
        out_pipe = os.popen(pdf_to_text_cmd, mode="r")
        pdf_text = ""
        lines = out_pipe.readlines()
        for line in lines:
            pdf_text += '> ' + line.replace('>', r'\>')
        os.remove(tmp_file_name)
        return pdf_text