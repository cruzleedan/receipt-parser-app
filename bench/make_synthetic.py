"""Render a fictional receipt to verify tender selection and 12-item completeness."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main(font_path,out):
    lines=["EXAMPLE GROCERY", "FICTIONAL TEST RECEIPT", "Date: 11/17/2026 10:30", ""]
    lines += [f"Item {i:02d}        1 x 5.00       5.00" for i in range(1,12)]
    lines += ["Item 12        1 x 25.00     25.00", "", "SUBTOTAL                  80.00",
              "VAT included               8.57", "AMOUNT DUE PHP            80.00",
              "CASH                     100.00", "CHANGE                    20.00"]
    image=Image.new("RGB",(760,len(lines)*42+60),"white")
    draw=ImageDraw.Draw(image)
    font=ImageFont.truetype(font_path,27)
    for index,line in enumerate(lines):
        draw.text((25,25+index*42),line,font=font,fill="black")
    image.save(out)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--font",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    main(args.font,args.out)
