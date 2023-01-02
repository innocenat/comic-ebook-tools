Comic EBOOK tools and calibre integration
=========================================

This is a set of script to help manage and convert
comics file along with calibre integration via
the content server.

## Features

- Read EPUB, AZW3, CBZ, PDF file
- Write EPUB, CBZ, PDF file
- Manage metadata and table of contents across all formats
- Integrated with calibre via content server (NOT a plugin)

## Requirement

The program require Python, probably 3.10+ (I don't know which version is actually required).
ImageMagick is required for PDF input (not required for PDF output)

## Usage

This tools is intended for command line usage.

### Installation

Download and/or clone the repository and use pip to install dependencies.

    $ pip install -r requirements.txt

### Convert specific file

Use the `script-comic.py`.

     script-comic.py [--width=WIDTH] [--height=HEIGHT] [--rtl] input output
     Supported input: folder, zip, cbz, pdf, epub, azw3
     Supported output: cbz, zip, pdf, epub

### Convert from calibre library

First, make sure to start the calibre content server. Then use the `script-calibre-comic.py`.

    script-calibre-comic.py [--library=LIBRARY_PATH] [--format=FORMAT] [--rtl]
    [--no-process] [--width=WIDTH] [--height=HEIGHT]
    [--quality=60] [ids [ids [...]]]
    
    --library=URL      Specified library path to calibre content server to pass to
                       calibredb tool.
    --rtl              Specified that the comic is read from left to right.
                       Only apply to CBZ input, otherwise the direction
                       is read from the source file.
    --format=FORMAT    Output format. PDF or CBZ or EPUB (default)
    --no-process       Disable image processing
    --width, --height  Target image width. Default is 1404 by 1872 (7.8" 300ppi).
                       Only if image processing is enabled.
    --quality=QUALITY  JPEG quality to save. Default 60. [1-100]
                       Only if image processing is enabled.
    ids                Calibre's book id to convert.
                       This script will prefer format in the order of
                       AZW3, CBZ, PDF, EPUB as the input.

### cbz-meta.html

This is a simple tool to help adding ComicInfo.xml metadata to the
CBZ file. Cannot be run directly -- require a local server.

## Technical detail

### Image processing

Several image processing are performed on the comic. This can be adjusted 
manually in the code, but currently it cannot be adjusted from the provided script.

- Heuristic merge of page spread.
  - The program calculate contrast at the edge of each spread to decide if it is actually a full spread.
- Margin cropping
  - Crop empty border.
- Gamma correction and dithering
  - Apply gamma correction and dither the image to 4-bit greyscale.
- Page spread split

Implementation detail is available in `comicprocessor.py`.

### CBZ / ZIP (and Folder input)

The metadata is read from the CBZ/ZIP comment as the ComicBookInfo format. Metadata from here
does not contain Table of Content.

The script also read from ComicInfo.xml metadata. Here, the bookmarks are treated as
table of contents, the same way as Kindle Comic Converter does. However, folder structure
is not considered for the table of content.

Reading direction (LTR/RTL) is not stored nor read. This should be passed to the program
as a parameter.

### EPUB/AZW3

AZW3 is internally converted to EPUB using KindleUnpack. EPUB produced by this script
is valid Kindle Comic EPUB.

### PDF

PDF is currently read using ImageMagick to convert each page individually to image. This
is a very slow process. Reading direction is read from the file, however, currently
metadata and table of content is not read.

Table of content and reading is written to the output file. But non-latin may
not display correctly in Adobe Reader.

## Copyright

This program is licensed under GNU General Public License 3.0 or later. The distribution include
the KindleUnpack program available from https://github.com/kevinhendricks/KindleUnpack.
