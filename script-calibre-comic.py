#!/usr/bin/env python3

import os
import calibredb
import comicbook
import comicprocessor

ABOUT = """
This script is to automate the conversion of comic filed
from one format to another format in calibre library.

Usage:
 script-calibre-comic.py [--library=LIBRARY_PATH] [--format=FORMAT] [--rtl]
                         [--no-process] [--width=WIDTH] [--height=HEIGHT] 
                         [--quality=60] [ids [ids [...]]]

--library=URL      Specified library path to calibre content server to pass to
                   calibredb tool.
--rtl              Specified that the comic is read from left to right.
                   Only apply to CBZ input, otherwise the direction
                   is read from the source file.
--format=FORMAT    Output format. PDF or CBZ or EPUB (default)

--color            Retain color
--no-process       Disable image processing
--width, --height  Target image width. Default is 1404 by 1872 (7.8" 300ppi).
                   Only if image processing is enabled.
--quality=QUALITY  JPEG quality to save. Default 60. [1-100]
                   Only if image processing is enabled.
                   
ids                Calibre's book id to convert.
                   This script will prefer format in the order of 
                   AZW3, CBZ, PDF, EPUB as the input.
"""


def main(ids):
    width = 1404
    height = 1872
    library = None
    rtl = False
    color = False
    quality = 60
    image_processing = True
    output_format = 'EPUB'

    # Parse parameter
    ids = ids[1:]
    while True:
        # Poorsman argument parser
        if len(ids) == 0:
            print(ABOUT)
            return

        if ids[0][:2] != '--':
            break

        values = ids[0][2:].split('=', 1)
        k = values[0]
        v = values[1] if len(values) == 2 else None

        if k == 'width':
            width = int(v)
        elif k == 'height':
            height = int(v)
        elif k == 'library':
            library = v
        elif k == 'rtl':
            rtl = True
        elif k == 'ltr':
            rtl = False
        elif k == 'color':
            color = True
        elif k == 'no-process':
            image_processing = False
        elif k == 'quality':
            quality = int(v)
            if quality < 1 or quality > 100:
                print(ABOUT)
                return
        elif k == 'format':
            v = v.lower()
            if v not in ['epub', 'cbz', 'pdf']:
                print(ABOUT)
                return
            output_format = v
        else:
            print(ABOUT)
            return

        ids = ids[1:]

    db = calibredb.CalibreDB(library=library)
    formats = ['AZW3', 'CBZ', 'PDF', 'EPUB']

    for id_ in ids:
        book = db.search(id_)

        if len(book) == 0:
            print('Cannot find book id {}'.format(id_))
            continue

        book = book[0]
        print('Book: {}'.format(book['title']))

        selected_format = None
        for current_format in formats:
            if db.book_has_format(book, current_format):
                selected_format = current_format
                break

        if selected_format is None:
            print('No available format (AZW3/CBZ/PDF/EPUB), skipping.')
            continue

        print('Loading from calibre...')
        print(db.save(id_, selected_format))
        input_file = '{}.{}'.format(id_, selected_format.lower())
        output_file = '{}.{}'.format(id_, output_format)

        print('Reading book information...')
        book = comicbook.load_book(input_file)

        # Only specify direction for CBZ
        if selected_format == 'CBZ':
            book.direction = -1 if rtl else 1

        print('Pages: {}'.format(len(book.images)))

        if image_processing:
            print('Processing...')
            processor = comicprocessor.ComicProcessor(dir=book.direction, resize=(width, height), color=color)
            output = comicbook.process_comic(book, processor, quality)
        else:
            output = book

        print('Saving as {}...'.format(output_format.upper()))
        if output_format == 'epub':
            comicbook.write_as_epub(output, output_file)
        elif output_format == 'cbz':
            comicbook.write_as_zip(output, output_file)
        elif output_format == 'pdf':
            comicbook.write_as_pdf(output, output_file)

        print('Adding to calibre...')
        print(db.add_book_format(id_, output_file))

        print('Cleanup...')
        os.remove(input_file)
        os.remove(output_file)

        print('Done!')


if __name__ == '__main__':
    import sys

    main(sys.argv)
