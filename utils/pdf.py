import os
import glob
import tempfile
from typing import IO

from utils.ocr import run_image_ocr


def get_pdf_full_text(pdf_file_like: IO) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file_name = f"{tmpdir}/tmp.pdf"
        with open(tmp_file_name, mode="wb") as pdf_file:
            pdf_file.write(pdf_file_like.read())

        pdf_to_text_cmd = f"pdftotext -nopgbrk -layout '{tmp_file_name}' -"
        pdf_text = ""
        out_pipe = os.popen(pdf_to_text_cmd, mode="r")
        lines = out_pipe.readlines()
        for line in lines:
            pdf_text += '> ' + line.replace('>', r'\>')

        if len(pdf_text.strip()) == 0:
            pdfimage_cmd = f"pdfimages -tiff '{tmp_file_name}' '{tmpdir}/image'"
            if os.system(pdfimage_cmd) != 0:
                print("Failed to run pdfimage command")
                return ""

            for file in sorted(glob.glob(f"{tmpdir}/image-*")):
                image_txt = run_image_ocr(file)
                if len(image_txt) > 0:
                    pdf_text += image_txt

        os.remove(tmp_file_name)

        return pdf_text
