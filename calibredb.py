#!/usr/bin/env python3

import subprocess
import json


class CalibreDB:
    def __init__(self, library=None):
        self.library_cmd = '--with-library={}'.format(library) if library is not None else ''

    def raw_cmd(self, cmd):
        command = 'calibredb {} {}'.format(self.library_cmd, cmd)
        return subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).stdout.read().decode('utf-8')

    def search(self, id):
        cmd = 'list --fields title,formats --for-machine --search id:{}'
        return json.loads(self.raw_cmd(cmd.format(id)))

    def save(self, id, format):
        cmd = 'export --dont-save-cover --dont-write-opf --formats {} --single-dir --template "{{id}}" {}'
        return self.raw_cmd(cmd.format(format, id))

    def add_book_format(self, book_id, file):
        return self.raw_cmd('add_format {} "{}"'.format(book_id, file))

    def book_has_format(self, book, book_format):
        for s in book['formats']:
            if len(s) >= len(book_format):
                if s[-len(book_format):].lower() == book_format.lower():
                    return True
