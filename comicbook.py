#!/usr/bin/env python3

import tempfile
import os
import sys
from lxml import etree
import zipfile
import json
from datetime import datetime
import glob

import kindleunpack.kindleunpack


def parse_xml(file):
    parser = etree.XMLParser(recover=True)
    xml = etree.parse(file, parser=parser)
    return xml


class ComicMetadata:
    writer_synonyms = ['writer', 'plotter', 'scripter']
    penciller_synonyms = ['artist', 'penciller', 'penciler', 'breakdowns']
    inker_synonyms = ['inker', 'artist', 'finishes']
    colorist_synonyms = ['colorist', 'colourist', 'colorer', 'colourer']
    letterer_synonyms = ['letterer']
    cover_synonyms = ['cover', 'covers', 'coverartist', 'cover artist']
    editor_synonyms = ['editor']

    def __init__(self):
        self.title = None
        self.credits = []
        self.series = None
        self.volume = None
        self.count = None
        self.year = None
        self.month = None
        self.publisher = None
        self.language = None
        self.summary = None

        self.toc = []
        self.spread_map = []

    def map_toc(self, page_map):
        for i in range(len(self.toc)):
            old_page = self.toc[i][0]
            new_page = old_page

            # Find in page map
            # Pages should not be that high so just do O(n^2)
            for a, b in page_map:
                if a == old_page:
                    new_page = b
                    break

            self.toc[i][0] = new_page

    # Read from EPUB/AZW3 OPF file from LXML ETree
    def read_opf_tree(self, tree):
        root = tree.getroot()

        xmlns = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/',
        }

        def read_from_xml(tag_name):
            elem = root.find('.//{}'.format(tag_name), xmlns)
            if elem is not None:
                return elem.text
            return None

        self.title = read_from_xml('dc:title')
        self.publisher = read_from_xml('dc:publisher')
        self.language = read_from_xml('dc:language')

        for tag in root.findall('.//dc:creator', xmlns):
            self.credits.append({
                'person': tag.text,
                'role': 'artist'
            })

        for tag in root.findall('.//meta'):
            if tag.get('name') == 'calibre:series':
                self.series = tag.get('content')
            if tag.get('name') == 'calibre:series_index':
                self.volume = int(float(tag.get['content']))

        date = read_from_xml('dc:date')
        if date:
            dt = datetime.fromisoformat(date)

            self.year = dt.year
            self.month = dt.month

    def read_ncx(self, tree, images_list):
        # Table of content
        toc = []
        try:
            root = tree.getroot()

            xmlns = {
                'ncx': 'http://www.daisy.org/z3986/2005/ncx/',
            }

            for nav_point in root.findall('./ncx:navMap/ncx:navPoint', xmlns):
                title = nav_point.find('./ncx:navLabel/ncx:text', xmlns).text
                href = nav_point.find('./ncx:content', xmlns).get('src')
                order = nav_point.get('playOrder')
                toc.append((title, href, order))
        except:
            return

        toc.sort(key=lambda x: int(x[2]))

        if len(toc) == 0:
            return []

        flat_toc = []
        toc_idx = 0
        cnt = 0
        for file, src in images_list:
            if file == toc[toc_idx][1]:
                flat_toc.append([cnt, toc[toc_idx][0]])
                toc_idx += 1

                if toc_idx == len(toc):
                    break

            cnt += 1

        self.toc = flat_toc

    def generate_opf(self):
        raise NotImplementedError()

    def generate_ncx(self):
        raise NotImplementedError()

    # ComicInfoXML
    # https://github.com/anansi-project/comicinfo
    # https://github.com/anansi-project/comicinfo/blob/main/schema/v2.0/ComicInfo.xsd
    # https://github.com/ciromattia/kcc/wiki/ComicRack-metadata
    def read_comicinfoxml(self, tree):
        root = tree.getroot()

        def read_from_xml(tag):
            el = root.find('.//{}'.format(tag))
            if el is not None and len(el) > 0:
                return el.text
            return None

        def read_credit(tag, role):
            el = root.find('.//{}'.format(tag))
            if el is not None and len(el) > 0:
                self.credits.append({
                    'person': el.text,
                    'role': role
                })

        self.title = read_from_xml('Title')
        self.series = read_from_xml('Series')
        self.volume = read_from_xml('Volume')
        self.count = read_from_xml('Count')
        self.year = read_from_xml('Year')
        self.month = read_from_xml('Month')
        self.publisher = read_from_xml('Publisher')
        self.language = read_from_xml('LanguageISO')
        self.summary = read_from_xml('Summary')

        self.credits = []
        read_credit('Writer', 'Writer')
        read_credit('Penciller', 'Penciller')
        read_credit('Inker', 'Inker')
        read_credit('Colorist', 'Colorer')
        read_credit('Letterer', 'Leterrer')
        read_credit('CoverArtist', 'Cover')
        read_credit('Editor', 'Editor')

        self.toc = []
        for elem in root.findall('.//Page'):
            if elem.get('Bookmark'):
                self.toc.append([int(elem.get('Image')), elem.get('Bookmark')])

    def generate_comicinfoxml(self):
        xml = '<?xml version="1.0" encoding="utf-8"?>\n'
        xml += '<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        if self.title:
            xml += '\t<Title><![CDATA[{}]]></Title>\n'.format(self.title)
        if self.series:
            xml += '\t<Series><![CDATA[{}]]></Series>\n'.format(self.series)
        if self.volume:
            xml += '\t<Volume>{}</Volume>\n'.format(self.volume)
        if self.count:
            xml += '\t<Count>{}</Count>\n'.format(self.count)
        if self.year:
            xml += '\t<Year>{}</Year>\n'.format(self.year)
        if self.month:
            xml += '\t<Month>{}</Month>\n'.format(self.month)
        if self.publisher:
            xml += '\t<Publisher><![CDATA[{}]]></Publisher>\n'.format(self.publisher)
        if self.language:
            xml += '\t<LanguageISO>{}</LanguageISO>\n'.format(self.language)
        if self.summary:
            xml += '\t<Summary><![CDATA[{}]]></Summary>\n'.format(self.summary)

        for people in self.credits:
            if people['role'].lower() in self.writer_synonyms:
                xml += '\t<Writer><![CDATA[{}]]></Writer>\n'.format(people['person'])
            if people['role'].lower() in self.penciller_synonyms:
                xml += '\t<Penciller><![CDATA[{}]]></Penciller>\n'.format(people['person'])
            if people['role'].lower() in self.inker_synonyms:
                xml += '\t<Inker><![CDATA[{}]]></Inker>\n'.format(people['person'])
            if people['role'].lower() in self.colorist_synonyms:
                xml += '\t<Colorist><![CDATA[{}]]></Colorist>\n'.format(people['person'])
            if people['role'].lower() in self.letterer_synonyms:
                xml += '\t<Letterer><![CDATA[{}]]></Letterer>\n'.format(people['person'])
            if people['role'].lower() in self.cover_synonyms:
                xml += '\t<CoverArtist><![CDATA[{}]]></CoverArtist>\n'.format(people['person'])
            if people['role'].lower() in self.editor_synonyms:
                xml += '\t<Editor><![CDATA[{}]]></Editor>\n'.format(people['person'])

        if len(self.toc) > 0:
            xml += '\t<Pages>\n'
            for item in self.toc:
                xml += '\t\t<Pages Image="{}" Bookmark="{}"/>\n'.format(item[0], item[1])
            xml += '\t</Pages>\n'

        xml += '</ComicInfo>\n'

        return xml

    # ComicBookInfo
    # https://code.google.com/archive/p/comicbookinfo/wikis/Example.wiki
    # https://github.com/dickloraine/EmbedComicMetadata/blob/master/comicinfoxml.py
    def read_comicbookinfo(self, json_string):
        try:
            container = json.loads(json_string)
        except:
            return False

        if 'ComicBookInfo/1.0' not in container:
            return False

        metadata = container['ComicBookInfo/1.0']

        def read_from_json(value):
            if value in metadata:
                return metadata[value]
            else:
                return None

        self.credits = read_from_json('credits')
        self.title = read_from_json('title')
        self.series = read_from_json('series')
        self.volume = read_from_json('volume')
        self.count = read_from_json('numberOfVolumes')
        self.year = read_from_json('publicationYear')
        self.month = read_from_json('publicationMonth')
        self.publisher = read_from_json('publisher')
        self.language = read_from_json('language')
        self.summary = read_from_json('comments')

        if self.credits is None:
            self.credits = []

        return True

    def generate_comicbookinfo(self):
        metadata = {}

        if self.title:
            metadata['title'] = self.title

        if len(self.credits) > 0:
            metadata['credits'] = self.credits

        if self.series:
            metadata['series'] = self.series

        if self.volume:
            metadata['volume'] = self.volume

        if self.count:
            metadata['numberOfVolumes'] = self.count

        if self.year:
            metadata['publicationYear'] = self.year

        if self.month:
            metadata['publicationMonth'] = self.month

        if self.publisher:
            metadata['publisher'] = self.publisher

        if self.language:
            metadata['language'] = self.language

        if self.summary:
            metadata['comments'] = self.summary

        container = {
            'appID': 'github.com/innocenat/comic-book-tools/dev',
            'lastModified': str(datetime.now()),
            'ComicBookInfo/1.0': metadata
        }

        return json.dumps(container)


class ComicBook:
    def __init__(self):
        self.metadata = ComicMetadata()
        self.images = []
        self.direction = 1

        self._dir = tempfile.TemporaryDirectory()
        self.dir_name = self._dir.name

    def close(self):
        self._dir.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()


class EPUBComicReader(ComicBook):
    def __init__(self, book_file):
        super().__init__()

        self._extract_book(book_file)

        # Find OPF file
        opf_file = self._find_opf()

        # Read OPF file
        self.images = self._read_opf(opf_file)

    def _find_opf(self):
        container_xml = os.path.join(self.dir_name, 'META-INF', 'container.xml')
        tree = parse_xml(container_xml)
        root = tree.getroot()

        for rootfile in root.findall('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile'):
            if rootfile.get('media-type') == 'application/oebps-package+xml':
                return rootfile.get('full-path')

        raise Exception('Cannot find OPF file in META-INF/container.xml')

    def _read_opf(self, opf_file):
        opf_xml = os.path.join(self.dir_name, opf_file)
        tree = parse_xml(opf_xml)
        root = tree.getroot()

        # Read metadata
        self.metadata.read_opf_tree(tree)

        xmlns = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'xhtml': 'http://www.w3.org/1999/xhtml',
            'svg': 'http://www.w3.org/2000/svg',
            'xlink': 'http://www.w3.org/1999/xlink',
        }

        # Read spine
        spine = root.find('.//opf:spine', xmlns)
        spine_list = []
        for itemref in spine.findall('.//opf:itemref', xmlns):
            idref = itemref.get('idref')
            item = root.find('.//opf:item[@id="{}"]'.format(idref), xmlns)
            href = item.get('href')
            spine_list.append(href)

        # Read direction
        for spine in root.findall('.//opf:spine', xmlns):
            if spine.get('page-progression-direction') == 'rtl':
                self.direction = -1

        # Read image from each page in spine
        base_path = os.path.join(self.dir_name, os.path.dirname(opf_xml))

        images_list = []
        for page in spine_list:
            page_path = os.path.join(base_path, page)
            tree = parse_xml(page_path)
            page_root = tree.getroot()
            found_image = False

            # Read SVG image first
            for img in page_root.findall('.//svg:image', xmlns):
                src = img.get('{{{}}}href'.format(xmlns['xlink']))
                src = os.path.join(os.path.dirname(page_path), src)
                images_list.append((page, src))
                found_image = True

            if not found_image:
                # Find using XHTML img tag instead
                for img in page_root.findall('.//xhtml:img', xmlns):
                    src = img.get('src')
                    src = os.path.join(os.path.dirname(page_path), src)
                    images_list.append((page, src))
                    found_image = True

            if not found_image:
                # Find using html img tag instead
                for img in page_root.findall('.//img', xmlns):
                    src = img.get('src')
                    src = os.path.join(os.path.dirname(page_path), src)
                    images_list.append((page, src))
                    found_image = True

        try:
            ncx_id = root.find('.//opf:spine', xmlns).get('toc')
            ncx_item = root.find('.//opf:item[@id="{}"]'.format(ncx_id), xmlns).get('href')
            ncx_xml = os.path.join(base_path, ncx_item)

            self.metadata.read_ncx(parse_xml(ncx_xml), images_list)
        except:
            pass

        return [x[1] for x in images_list]

    def _extract_book(self, book_file):
        with zipfile.ZipFile(book_file, 'r') as epub_zip:
            epub_zip.extractall(path=self.dir_name)


class AZW3ComicReader(EPUBComicReader):
    def _extract_book(self, book_file):
        # Block print
        sys.stdout = open(os.devnull, 'w')
        kindleunpack.kindleunpack.unpackBook(book_file, self.dir_name)
        sys.stdout = sys.__stdout__

        self.dir_name = os.path.join(self.dir_name, 'mobi8')


class DirComicReader(ComicBook):
    def __init__(self, book_file):
        super().__init__()
        self._prepare_book_folder(book_file)

        # Try finding ComicInfo.xml
        for file in glob.glob(os.path.join(self.dir_name, '**', 'ComicInfo.xml'), recursive=True):
            self.metadata.read_comicinfoxml(parse_xml(file))

        # Find all images
        files = [x for e in ['jpg', 'jpeg', 'png', 'gif'] for x in
                 glob.glob(os.path.join(self.dir_name, '**', '*.{}'.format(e)), recursive=True)]
        files.sort()

        self.images = files

    def _prepare_book_folder(self, book_file):
        self.dir_name = book_file


class ZipComicReader(DirComicReader):
    def _prepare_book_folder(self, book_file):
        with zipfile.ZipFile(book_file, 'r') as zfp:
            zfp.extractall(path=self.dir_name)
            self.metadata.read_comicbookinfo(zfp.comment.decode('utf-8'))


class PDFComicReader(DirComicReader):
    def _prepare_book_folder(self, book_file):
        import pikepdf

        magick = 'magick convert' if os.name == 'nt' else 'convert'
        magick_command = '{} -density 600 "{}" -quality 100 "{}"'
        command = magick_command.format(magick, book_file, os.path.join(self.dir_name, 'output.png'))
        os.system(command)

        # Read RTL direction
        with pikepdf.Pdf.open(book_file) as pdf:
            if pdf.Root.ViewerPreferences.Direction == pikepdf.Name.R2L:
                self.direction = -1

        # TODO read bookmarks as table of content


def write_as_zip(book, output):
    with zipfile.ZipFile(output, 'w') as zfp:
        # Write metadata
        zfp.comment = bytes(book.metadata.generate_comicbookinfo(), 'utf-8')
        zfp.writestr('ComicInfo.xml', book.metadata.generate_comicinfoxml())

        # Write image
        for image in book.images:
            zfp.write(image, os.path.basename(image))


def write_as_epub(book, output):
    from PIL import Image
    import uuid
    from xml.sax.saxutils import escape

    book_id = uuid.uuid4()

    def html_name(image):
        return os.path.splitext(os.path.basename(image))[0] + '.xhtml'

    def image_id(image):
        i = os.path.splitext(os.path.basename(image))[0]
        if i == '00000':
            return 'i-cover'
        return 'i-' + i

    def html_id(image):
        i = os.path.splitext(os.path.basename(image))[0]
        if i == '00000':
            return 'p-cover'
        return 'p-' + i

    def write_container():
        xml = ''
        xml += '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        xml += '\t<rootfiles>\n'
        xml += '\t\t<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
        xml += '\t</rootfiles>'
        xml += '</container>\n'

        return xml

    def write_style():
        style = ''
        style += '@charset "UTF-8";\n'
        style += '\n'
        style += '@page {\n'
        style += 'margin: 0;\n'
        style += '}\n'
        style += '\n'
        style += 'html, body, div {\n'
        style += 'display:   block;\n'
        style += 'margin:    0;\n'
        style += 'padding:   0;\n'
        style += 'font-size: 0;\n'
        style += '}\n'
        style += '\n'
        style += 'svg {\n'
        style += 'margin:    0;\n'
        style += 'padding:   0;\n'
        style += '}\n'

        return style

    def write_opf():
        with Image.open(book.images[0]) as im:
            w, h = im.size

        opf = ''
        opf += '<?xml version="1.0" encoding="utf-8"?>\n'
        opf += '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">\n'
        opf += '\t<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">\n'
        if book.metadata.title:
            opf += '\t\t<dc:title>{}</dc:title>\n'.format(escape(book.metadata.title))
        for people in book.metadata.credits:
            opf += '\t\t<dc:creator opf:role="aut">{}</dc:creator>\n'.format(escape(people['person']))
        opf += '\t\t<dc:identifier id="uid">{}</dc:identifier>\n'.format(book_id)
        if book.metadata.publisher:
            opf += '\t\t<dc:publisher>{}</dc:publisher>\n'.format(escape(book.metadata.publisher))
        if book.metadata.month and book.metadata.year:
            dt = datetime(book.metadata.year, book.metadata.month, 1)
            opf += '\t\t<dc:date>{}</dc:date>\n'.format(dt.isoformat())
        if book.metadata.language:
            opf += '\t\t<dc:language>{}</dc:language>\n'.format(book.metadata.language)
        if book.metadata.summary:
            opf += '\t\t<dc:dc:description>{}</dc:dc:description>\n'.format(escape(book.metadata.summary))
        opf += '\t\t<meta name="cover" content="i-cover"/>\n'
        opf += '\t\t<meta name="output encoding" content="utf-8"/>\n'
        opf += '\t\t<meta name="RegionMagnification" content="false"/>\n'
        opf += '\t\t<meta name="book-type" content="comic"/>\n'
        if book.direction == 1:
            opf += '\t\t<meta name="primary-writing-mode" content="horizontal-lr"/>\n'
        else:
            opf += '\t\t<meta name="primary-writing-mode" content="vertical-rl"/>\n'
        opf += '\t\t<meta name="fixed-layout" content="true"/>\n'
        opf += '\t\t<meta name="orientation-lock" content="none"/>\n'
        opf += '\t\t<meta property="rendition:orientation">portrait</meta>\n'
        opf += '\t\t<meta property="rendition:spread">landscape</meta>\n'
        opf += '\t\t<meta property="rendition:layout">pre-paginated</meta>\n'
        opf += '\t\t<meta name="original-resolution" content="{}x{}"/>\n'.format(w, h)
        if book.metadata.series:
            opf += '\t\t<meta name="calibre:series" content="{}"/>\n'.format(escape(book.metadata.series))
        if book.metadata.volume:
            opf += '\t\t<meta name="calibre:series_index" content="{}"/>\n'.format(escape(book.metadata.volume))
        opf += '\t</metadata>\n'

        opf += '\t<manifest>\n'
        for img in book.images:
            opf += '\t\t<item id="{}" media-type="application/xhtml+xml" href="Text/{}"/>\n'.format(html_id(img),
                                                                                                    html_name(img))
        opf += '\t\t<item id="ncx" media-type="application/x-dtbncx+xml" href="toc.ncx"/>\n'
        opf += '\t\t<item id="book-css" media-type="text/css" href="Styles/style.css"/>\n'
        for img in book.images:
            opf += '\t\t<item id="{}" media-type="image/jpeg" href="Images/{}"/>\n'.format(image_id(img),
                                                                                           os.path.basename(img))
        opf += '\t</manifest>\n'

        page_side = -1
        opf += '\t<spine toc="ncx">\n' if book.direction == 1 else '\t<spine page-progression-direction="rtl" toc="ncx">\n'
        for idx, img in enumerate(book.images):
            if idx == 0:
                spread = 2
                page_side = -1
            elif idx in book.metadata.spread_map:
                spread = book.metadata.spread_map[idx]
                page_side = -1
            else:
                spread = page_side
                page_side = -page_side

            if book.direction == 1:
                spread = 'center' if spread == 2 else 'left' if spread == -1 else 'right'
            else:
                spread = 'center' if spread == 2 else 'left' if spread == 1 else 'right'

            opf += '\t\t<itemref idref="{}" linear="yes" properties="page-spread-{}"/>\n'.format(html_id(img), spread)
        opf += '\t</spine>\n'

        opf += '\t<tours></tours>\n'
        opf += '\t<guide></guide>\n'

        opf += '</package>\n'

        return opf

    def write_ncx():
        ncx = ''
        ncx += '<?xml version="1.0" encoding="utf-8"?>\n'
        ncx += '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="ja">\n'
        ncx += '\t<head>\n'
        ncx += '\t\t<meta name="dtb:uid" content="{}"/>\n'.format(book_id)
        ncx += '\t\t<meta name="dtb:depth" content="1"/>\n'
        ncx += '\t\t<meta name="dtb:totalPageCount" content="0"/>\n'
        ncx += '\t\t<meta name="dtb:maxPageNumber" content="0"/>\n'
        ncx += '\t</head>\n'
        ncx += '\t<docTitle>\n'
        ncx += '\t\t<text>{}</text>\n'
        ncx += '\t</docTitle>\n'
        ncx += '\t<navMap>\n'
        for idx, [page, title] in enumerate(book.metadata.toc):
            ncx += '\t\t<navPoint id="np_{0}" playOrder="{0}">\n'.format(idx + 1)
            ncx += '\t\t\t<navLabel>\n'
            ncx += '\t\t\t\t<text>{}</text>\n'.format(title)
            ncx += '\t\t\t</navLabel>\n'
            ncx += '\t\t\t<content src="Text/{}"/>\n'.format(html_name(book.images[page]))
            ncx += '\t\t</navPoint>\n'
        ncx += '\t</navMap>\n'
        ncx += '</ncx>\n'

        return ncx

    def write_html(image, is_cover=False):
        with Image.open(image) as im:
            w, h = im.size

        html = ''
        html += '<?xml version="1.0" encoding="UTF-8"?>\n'
        html += '<!DOCTYPE html>\n'
        html += '<html xmlns=\'http://www.w3.org/1999/xhtml\' xmlns:epub=\'http://www.idpf.org/2007/ops\'>\n'
        html += '<head>\n'
        html += '\t<meta charset="UTF-8"/>\n'
        html += '\t<title>{}</title>\n'.format(image)
        html += '\t<link href="../Styles/style.css" type="text/css" rel="stylesheet"/>\n'
        html += '\t<meta name="viewport" content="width={}, height={}"/>\n'.format(w, h)
        html += '</head>\n'
        html += '<body epub:type="cover">\n' if is_cover else '<body>\n'
        html += '\t<div class="main">\n'
        html += '\t\t<svg xmlns="http://www.w3.org/2000/svg" version="1.1" xmlns:xlink="http://www.w3.org/1999/xlink" width="100%" height="100%" viewBox="0 0 {} {}">\n'.format(
            w, h)
        html += '\t\t\t<image width="{}" height="{}" xlink:href="../Images/{}"/>\n'.format(w, h,
                                                                                           os.path.basename(image))
        html += '\t\t</svg>\n'
        html += '\t</div>\n'
        html += '</body>\n'
        html += '</html>\n'

        return html

    with zipfile.ZipFile(output, 'w') as zfp:
        zfp.writestr('mimetype', 'application/epub+zip', compresslevel=zipfile.ZIP_STORED)
        zfp.writestr('META-INF/container.xml', write_container())
        zfp.writestr('OEBPS/content.opf', write_opf())
        zfp.writestr('OEBPS/toc.ncx', write_ncx())

        # Stylesheet
        zfp.writestr('OEBPS/Styles/style.css', write_style())

        # Write pages
        for idx, image in enumerate(book.images):
            zfp.writestr('OEBPS/Text/' + html_name(image), write_html(image, idx == 0))

        # Write image
        for image in book.images:
            zfp.write(image, 'OEBPS/Images/' + os.path.basename(image))


def write_as_pdf(book, output):
    import pikepdf
    from PIL import Image
    from fpdf import FPDF, ViewerPreferences

    DEFAULT_DPI = 300
    DEFAULT_DPM = DEFAULT_DPI / 25.4

    pdf = FPDF()
    pdf.set_display_mode('fullpage', 'two')
    pdf.set_margin(0)
    pdf.viewer_preferences = ViewerPreferences(hide_toolbar=True, hide_menubar=False, fit_window=True)

    toc_map = {x[0]: x[1] for x in book.metadata.toc}

    for i, image in enumerate(book.images):
        img = Image.open(image)
        width, height = img.size

        # Convert directly to mm
        width /= DEFAULT_DPM
        height /= DEFAULT_DPM

        pdf.add_page(format=(width, height))
        pdf.image(img, 0, 0, width, height)

        # Create TOC if present
        if i in toc_map:
            pdf.start_section(toc_map[i])

    pdf.output(output)

    # Set RTL and two-column reading
    with pikepdf.Pdf.open(output, allow_overwriting_input=True) as pdf:
        pdf.Root.PageLayout = pikepdf.Name.TwoPageRight
        if book.direction == -1:
            pdf.Root.ViewerPreferences.Direction = pikepdf.Name.R2L
        pdf.save()


def process_comic(comic_book, processor, quality=60):
    output = ComicBook()
    output.direction = comic_book.direction
    output.images = processor.process(comic_book.images, output.dir_name, quality)
    output.metadata = comic_book.metadata

    if processor.page_map:
        output.metadata.map_toc(processor.page_map)

    if processor.spread_map:
        output.metadata.spread_map = processor.spread_map

    return output


def load_book(book_file):
    if os.path.isdir(book_file):
        return DirComicReader(book_file)

    _, ext = os.path.splitext(book_file)

    if ext == '.pdf':
        return PDFComicReader(book_file)
    elif ext == '.azw3' or ext == '.mobi':
        return AZW3ComicReader(book_file)
    elif ext == '.epub' or ext == '.epub2' or ext == '.epub3':
        return EPUBComicReader(book_file)
    elif ext == '.zip' or ext == '.cbz':
        return ZipComicReader(book_file)

    raise Exception('Unknown comic file {}'.format(ext))
