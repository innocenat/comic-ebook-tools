#!/usr/bin/env python3

import os
import comicbook
import comicprocessor

"""
This script is to convert comic from one format to another

Usage:
 script-comic.py [--width=WIDTH] [--height=HEIGHT] [--rtl] input output
 Supported input: folder, zip, cbz, pdf, epub, azw3
 Supported output: cbz, zip, pdf, epub
"""


def main(args):
    WIDTH = 1404
    HEIGHT = 1872
    RTL = False

    USAGE = """Usage:
 script-comic.py [--width=WIDTH] [--height=HEIGHT] [--rtl] input output
 Supported input: folder, zip, cbz, pdf, epub, azw3
 Supported output: cbz, zip, pdf, epub"""

    # Parse parameter
    args = args[1:]
    while True:
        if len(args) == 0:
            print(USAGE)
            return

        if args[0][:2] != '--':
            break

        values = args[0][2:].split('=', 1)
        k = values[0]
        v = values[1] if len(values) == 2 else None

        if k == 'width':
            WIDTH = int(v)
        elif k == 'height':
            HEIGHT = int(v)
        elif k == 'rtl':
            RTL = True
        elif k == 'ltr':
            RTL = False
        else:
            print(USAGE)
            return

        args = args[1:]

    if len(args) < 2:
        print(USAGE)
        return

    input_file = args[0]
    _, file_ext = os.path.splitext(input_file)
    file_ext = file_ext.lower()

    output_file = args[1]
    _, output_ext = os.path.splitext(output_file)
    output_ext = output_ext.lower()

    print(input_file)
    print(output_file)

    if file_ext not in ['', '.cbz', '.zip', '.pdf', '.azw3', '.mobi', '.epub', '.epub2', '.epub3']:
        print(USAGE)
        return

    if output_ext not in ['.cbz', '.zip', '.pdf', '.epub']:
        print(USAGE)
        return

    print('Input file: {}'.format(input_file))
    book = comicbook.load_book(input_file)

    # Only specify direction for CBZ/ZIP/DIR
    if file_ext == '.cbz' or file_ext == '.zip' or file_ext == '':
        book.direction = -1 if RTL else 1

    if output_ext != '.pdf':
        print('Processing...')
        processor = comicprocessor.ComicProcessor(dir=book.direction, resize=(WIDTH, HEIGHT))
        output = comicbook.process_comic(book, processor)
    else:
        output = book

    print('Saving...')
    if output_ext == '.epub':
        comicbook.write_as_epub(output, output_file)
    elif output_ext == '.pdf':
        comicbook.write_as_pdf(output, output_file)
    else:
        comicbook.write_as_zip(output, output_file)

    print('Done!')


if __name__ == '__main__':
    import sys

    main(sys.argv)
