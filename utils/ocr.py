import os
import tempfile
from typing import IO


def get_image_full_text(img_file_like: IO) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file_name = f"{tmpdir}/tmp.img"
        with open(tmp_file_name, mode="wb") as img_file:
            img_file.write(img_file_like.read())

        ocr_cmd = f"tesseract -l eng '{tmp_file_name}' -"
        out_pipe = os.popen(ocr_cmd, mode="r")
        img_text = ""
        lines = out_pipe.readlines()
        for line in lines:
            img_text += '> ' + line.replace('>', r'\>')

        os.remove(tmp_file_name)
        return img_text
