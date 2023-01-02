import {
  render,
  html,
  useState,
  useEffect,
  useRef,
  useCallback
} from 'https://unpkg.com/htm@3.1.0/preact/standalone.module.js'

const DEFAULT_META = {
  'title': '',
  'series': '',
  'volume': '',
  'year': '',
  'month': '',
  'publisher': '',
  'language': '',
  'summary': '',
  'writer': '',
}

const META_TITLE = [
  ['title', 'Title'],
  ['writer', 'Writer'],
  ['series', 'Series'],
  ['volume', 'Volume'],
  ['year', 'Pub. Year'],
  ['month', 'Pub. Month'],
  ['publisher', 'Publisher'],
  ['language', 'Language (ISO)'],
  ['summary', 'Summary'],
]

function escapeXml (unsafe) {
  return unsafe.replace(/[<>&'"]/g, function (c) {
    switch (c) {
      case '<':
        return '&lt;'
      case '>':
        return '&gt;'
      case '&':
        return '&amp;'
      case '\'':
        return '&apos;'
      case '"':
        return '&quot;'
    }
  })
}

function MetaItem ({ title, meta, value, setValue }) {
  return html`
      <label>
          <div>${title}</div>
          <div><input value="${value}" oninput="${(e) => setValue(meta, e.target.value)}"/></div>
      </label>
  `
}

function BookmarkItem ({ title, page, setPage, focusRef, edit, remove }) {
  const defocus = (e) => {
    if (e.key === 'Enter') {
      e.target.blur()
      e.preventDefault()
    }
  }
  return html`
      <li key="${page}"><label>#${page}: <input value="${title}"
                                                oninput="${(e) => {edit(page, e.target.value)}}" ref="${focusRef}"
                                                onkeydown="${defocus}"/>
          <button onclick="${() => {setPage(page)}}">→</button>
          <button onclick="${() => {remove(page)}}">×</button>
      </label>
      </li>
  `
}

function App () {
  const [images, setImages] = useState([])
  const [meta, setMeta] = useState({ ...DEFAULT_META })
  const [bookmarks, setBookmarks] = useState({})
  const [page, setPage] = useState(0)
  const [fname, setFname] = useState('')
  const fileSel = useRef(null)
  const toFocus = useRef(null)
  const [lastBook, setLastBook] = useState(-1)

  const sorted_keys = Object.keys(bookmarks).map(x => +x)
  sorted_keys.sort((a, b) => a - b)

  const readXML = (xml) => {
    const parser = new DOMParser()
    const tree = parser.parseFromString(xml, 'text/xml')

    const parseItem = (tag, meta) => {
      const t = tree.getElementsByTagName(tag)
      if (t.length > 0) {
        setMetaItem(meta, t[0].textContent)
      }
    }
    parseItem('Title', 'title')
    parseItem('Writer', 'writer')
    parseItem('Series', 'series')
    parseItem('Volume', 'volume')
    parseItem('Year', 'year')
    parseItem('Month', 'month')
    parseItem('Publisher', 'publisher')
    parseItem('LanguageISO', 'language')
    parseItem('Summary', 'summary')
    for (const page of tree.getElementsByTagName('Page')) {
      const pg = page.getAttribute('Image')
      const title = page.getAttribute('Bookmark')
      if (title) {
        editBookmark(pg, title)
      }
    }
  }

  const generateXML = () => {
    return `<?xml version="1.0" encoding="utf-8"?>
<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  ${meta.title ? `<Title>${escapeXml(meta.title)}</Title>` : ''}
  ${meta.writer ? `<Writer>${escapeXml(meta.writer)}</Writer>` : ''}
  ${meta.series ? `<Series>${escapeXml(meta.series)}</Series>` : ''}
  ${meta.volume ? `<Volume>${meta.volume}</Volume>` : ''}
  ${meta.year ? `<Year>${meta.year}</Year>` : ''}
  ${meta.month ? `<Month>${meta.month}</Month>` : ''}
  ${meta.publisher ? `<Publisher>${escapeXml(meta.publisher)}</Publisher>` : ''}
  ${meta.language ? `<LanguageISO>${meta.language}</LanguageISO>` : ''}
  ${meta.summary ? `<Summary>${escapeXml(meta.summary)}</Summary>` : ''}
  <Pages>
    ${sorted_keys.map(k => `<Page Image="${k}" Bookmark="${bookmarks[k]}"/>`).join('\n    ')}
  </Pages>
</ComicInfo>
`
  }

  const removeBookmark = useCallback((page) => {
    setBookmarks(c => {
      const copy = { ...c }
      delete copy[page]
      return copy
    })
  }, [setBookmarks])

  const addBookmark = useCallback((page) => {
    setBookmarks(c => {
      if (page in c) {
        return c
      }
      const copy = { ...c }
      copy[page] = ''
      return copy
    })
  }, [setBookmarks])

  const editBookmark = useCallback((page, title) => {
    setBookmarks(c => {
      const copy = { ...c }
      copy[page] = title
      return copy
    })
  }, [setBookmarks])

  const setMetaItem = useCallback((meta, value) => {
    setMeta(c => {
      const copy = { ...c }
      copy[meta] = value
      return copy
    })
  }, [setMeta])

  const doSetPage = useCallback((page) => {
    page = +page
    if (page < 0) page = 0
    if (page >= images.length) page = images.length - 1
    setPage(page)
  }, [setPage, images])

  const loadCBZ = useCallback(async (blob) => {
    try {
      // Load CBZ
      const reader = new zip.ZipReader(new zip.BlobReader(blob))
      const entries = await reader.getEntries()
      const images = []

      for (const entry of entries) {
        const filename = entry.filename
        const ext = filename.split('.').pop()
        if (['png', 'jpg', 'jpeg'].includes(ext)) {
          const bl = await entry.getData(new zip.BlobWriter())
          const u = URL.createObjectURL(bl)
          images.push([filename, u, bl])
        } else if (filename === 'ComicInfo.xml') {
          readXML(await entry.getData(new zip.TextWriter('utf-8')))
        }
      }

      images.sort((a, b) => a[0].localeCompare(b[0]))

      setImages(images)
      setPage(0)

    } catch (e) {
      console.error(e)
    }
  }, [setPage, setMeta, setBookmarks, setFname, setImages])

  const filePicked = useCallback(() => {
    const selectedFile = fileSel.current.files[0]
    setFname(selectedFile.name)
    loadCBZ(selectedFile)

  }, [fileSel])

  const saveFile = async () => {
    const blobWriter = new zip.BlobWriter('application/zip')
    const writer = new zip.ZipWriter(blobWriter, { extendedTimestamp: false })
    for (const img of images) {
      await writer.add(img[0], new zip.BlobReader(img[2]))
    }
    await writer.add('ComicInfo.xml', new zip.TextReader(generateXML()))
    await writer.close()

    const outputFile = await blobWriter.getData()
    saveAs(outputFile, fname)
  }

  const setPageDiff = useCallback((d) => {
    setPage((c) => {
      c += d
      if (c < 0)
        c = 0
      if (c >= images.length)
        c = images.length - 1
      return c
    })
  }, [setPage, images])

  const keyHandler = (e) => {
    if (e.target.tagName.toLowerCase() === 'input') {
      return true
    }
    switch (e.key) {
      case 'ArrowLeft':
        setPageDiff(-1)
        toFocus.current = null
        e.preventDefault()
        break
      case 'ArrowRight':
        setPageDiff(1)
        toFocus.current = null
        e.preventDefault()
        break
      case 'Enter':
        addBookmark(page)
        setLastBook(page)
        e.preventDefault()
        break
    }
  }

  useEffect(() => {
    window.addEventListener('keydown', keyHandler)
    return () => {
      window.removeEventListener('keydown', keyHandler)
    }
  })

  useEffect(() => {
    if (toFocus.current) {
      toFocus.current.focus()
    }
  })

  return html`
      <div class="left">
          <div class="nav">
              <button class="prev" onclick="${() => {doSetPage(page - 1)}}">←</button>
              Page <input type="number" value="${page}" onchange="${(e) => { doSetPage(e.target.value) }}"/>
              of ${images.length}
              <button class="next" onclick="${() => {doSetPage(page + 1)}}">→</button>
          </div>
          ${page < images.length && html`<img id="page-img" src="${images[page][1]}"/>`}
      </div>
      <div class="right">
          <section>
              <h2>File</h2>
              <div>Current file: ${fname || 'None'}</div>
              <div><input type="file" ref="${fileSel}" oninput="${filePicked}" accept=".zip,.cbz"/></div>
              <div>
                  <button onclick="${saveFile}">Save</button>
              </div>
          </section>
          <section>
              <h2>Metadata</h2>
              ${META_TITLE.map(([key, title]) => html`
                  <${MetaItem} title="${title}" meta="${key}" value="${meta[key]}" setValue="${setMetaItem}"/>`)}
          </section>
          <section>
              <h2>Bookmarks (Chapter)</h2>
              <ul>
                  ${sorted_keys.map((key) =>
                          key === lastBook ?
                                  html`
                                      <${BookmarkItem} title="${bookmarks[key]}" page="${key}"
                                                       setPage="${doSetPage}"
                                                       edit="${editBookmark}" focusRef="${toFocus}"
                                                       remove="${removeBookmark}"/>` :
                                  html`
                                      <${BookmarkItem} title="${bookmarks[key]}" page="${key}"
                                                       setPage="${doSetPage}"
                                                       edit="${editBookmark}" remove="${removeBookmark}"/>`
                  )}
                  <li>
                      <button onclick="${() => {addBookmark(page)}}">+ Add</button>
                  </li>
              </ul>
          </section>
      </div>
  `
}

function main (container) {
  render(html`
      <${App}/>`, container)
}

main(document.getElementById('main'))
