/*
 * Drag-and-drop ordering for the syllabus admin (papers, chapters and topics).
 *
 * Two places use it:
 *  - Inline tables on a scheme, paper or chapter page: rows are dragged, the sort_order inputs are renumbered and the
 *    editor presses Save as usual.
 *  - Change lists filtered to one parent (one scheme, paper or chapter): the new order is sent to the server at once
 *    and the visible sort_order inputs are updated, so a later "Save" of the list cannot bring back the old order.
 *
 * Keyboard: focus a row's handle and press Alt+Up or Alt+Down. No third-party code.
 */
(function () {
  'use strict'

  var HANDLE_LABEL = 'Drag to reorder. With the keyboard, press Alt and the up or down arrow.'
  var live = null

  function announce(message) {
    if (!live) {
      live = document.createElement('div')
      live.className = 'reorder-live'
      live.setAttribute('role', 'status')
      live.setAttribute('aria-live', 'polite')
      document.body.appendChild(live)
    }
    live.textContent = message
  }

  function csrfToken() {
    var field = document.querySelector('input[name=csrfmiddlewaretoken]')
    if (field) return field.value
    var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)
    return match ? decodeURIComponent(match[1]) : ''
  }

  function makeHandle() {
    var button = document.createElement('button')
    button.type = 'button'
    button.className = 'reorder-handle'
    button.setAttribute('aria-label', HANDLE_LABEL)
    button.title = 'Drag to reorder'
    button.textContent = '☰'
    return button
  }

  /** Adds a handle column to `table`. `rows()` returns the draggable rows in order, `onMoved(rows)` runs after a move. */
  function enhance(table, rows, onMoved) {
    var head = table.querySelector('thead tr')
    if (head && !head.querySelector('.reorder-head')) {
      var th = document.createElement('th')
      th.className = 'reorder-head'
      th.innerHTML = '<span class="reorder-head-text">Order</span>'
      head.insertBefore(th, head.firstChild)
    }
    rows().forEach(function (row) {
      addHandle(row, rows, onMoved)
    })
  }

  function addHandle(row, rows, onMoved) {
    if (row.querySelector('.reorder-handle') || row.classList.contains('empty-form')) return
    var cell = document.createElement(row.parentNode.tagName === 'THEAD' ? 'th' : 'td')
    cell.className = 'reorder-cell'
    var handle = makeHandle()
    cell.appendChild(handle)
    row.insertBefore(cell, row.firstChild)

    var before = null
    handle.addEventListener('mousedown', function () {
      row.draggable = true
    })
    handle.addEventListener('touchstart', function () {
      row.draggable = true
    })
    row.addEventListener('dragstart', function (event) {
      if (!row.draggable) return
      before = rows()
      row.classList.add('reorder-dragging')
      event.dataTransfer.effectAllowed = 'move'
      event.dataTransfer.setData('text/plain', 'reorder')
    })
    row.addEventListener('dragover', function (event) {
      var dragging = row.parentNode.querySelector('.reorder-dragging')
      if (!dragging || dragging === row) return
      event.preventDefault()
      var box = row.getBoundingClientRect()
      var after = event.clientY > box.top + box.height / 2
      row.parentNode.insertBefore(dragging, after ? row.nextSibling : row)
    })
    row.addEventListener('drop', function (event) {
      event.preventDefault()
    })
    row.addEventListener('dragend', function () {
      row.draggable = false
      row.classList.remove('reorder-dragging')
      var now = rows()
      if (before && now.some(function (r, i) { return r !== before[i] })) onMoved(now)
      before = null
    })
    handle.addEventListener('keydown', function (event) {
      if (!event.altKey || (event.key !== 'ArrowUp' && event.key !== 'ArrowDown')) return
      event.preventDefault()
      var list = rows()
      var index = list.indexOf(row)
      var target = list[index + (event.key === 'ArrowUp' ? -1 : 1)]
      if (!target) return
      row.parentNode.insertBefore(row, event.key === 'ArrowUp' ? target : target.nextSibling)
      handle.focus()
      var moved = rows()
      announce('Moved to position ' + (moved.indexOf(row) + 1) + ' of ' + moved.length)
      onMoved(rows())
    })
  }

  // --- inline tables: renumber the sort_order inputs, saved with the form ----------------------

  function sortInput(row) {
    return row.querySelector('input[name$="-sort_order"]')
  }

  function setupInline(group) {
    var table = group.querySelector('table')
    if (!table || !table.querySelector('input[name$="-sort_order"]')) return
    function rows() {
      return Array.prototype.slice.call(table.querySelectorAll('tbody tr.form-row')).filter(function (row) {
        return !row.classList.contains('empty-form') && sortInput(row)
      })
    }
    function renumber(list) {
      list.forEach(function (row, index) {
        var input = sortInput(row)
        if (input && input.value !== String(index)) {
          input.value = String(index)
          input.dispatchEvent(new Event('change', { bubbles: true }))
        }
      })
      announce('Order changed. Save the page to keep it.')
    }
    enhance(table, rows, renumber)
    document.addEventListener('formset:added', function (event) {
      var row = event.target
      if (row && table.contains(row)) addHandle(row, rows, renumber)
    })
  }

  // --- change lists: save the order on the server straight away --------------------------------

  function setupChangeList(config) {
    var table = document.getElementById('result_list')
    if (!table || !table.querySelector('input[name$="-sort_order"]')) return
    var intro = document.createElement('p')
    intro.className = 'help reorder-help'
    table.parentNode.insertBefore(intro, table)
    if (!config.enabled) {
      intro.textContent = config.hint
      return
    }
    intro.textContent = 'Drag the handle at the start of a row (or use Alt and the arrow keys) to change the order. It saves at once.'

    function rows() {
      return Array.prototype.slice.call(table.querySelectorAll('tbody tr')).filter(function (row) {
        return row.querySelector('input[type=hidden][name$="-id"]')
      })
    }
    function rowId(row) {
      return row.querySelector('input[type=hidden][name$="-id"]').value
    }
    function persist(list) {
      intro.textContent = 'Saving the new order…'
      fetch(config.url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
        body: JSON.stringify({ ids: list.map(rowId) }),
      })
        .then(function (response) {
          return response.json().then(function (body) {
            return { ok: response.ok, body: body }
          })
        })
        .then(function (result) {
          if (!result.ok) throw new Error((result.body && result.body.error) || 'Could not save the order.')
          list.forEach(function (row) {
            var input = sortInput(row)
            var value = result.body.orders[rowId(row)]
            if (input && value !== undefined) input.value = String(value)
          })
          intro.textContent = 'Order saved.' + (result.body.published ? ' This scheme is published: the change is live now.' : '')
          announce(intro.textContent)
        })
        .catch(function (error) {
          intro.textContent = error.message + ' Reload the page to see the saved order.'
          announce(intro.textContent)
        })
    }
    enhance(table, rows, persist)
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.inline-group').forEach(setupInline)
    var node = document.getElementById('reorder-config')
    if (node) setupChangeList(JSON.parse(node.textContent))
  })
})()
