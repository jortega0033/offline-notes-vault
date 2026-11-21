(function () {
  "use strict";

  var MAX_BODY = 100000;
  var API = "/api/v1";

  function $(id) { return document.getElementById(id); }

  var els = {
    search: $("search"),
    newNote: $("new-note"),
    list: $("note-list"),
    listState: $("list-state"),
    loadSample: $("load-sample"),
    title: $("note-title"),
    body: $("note-body"),
    count: $("body-count"),
    save: $("save"),
    status: $("status"),
    titleError: $("title-error"),
    conflict: $("conflict"),
    conflictMsg: $("conflict-message"),
    conflictActions: $("conflict-actions"),
    conflictReload: $("conflict-reload"),
    conflictOverwrite: $("conflict-overwrite"),
    conflictMineWrap: $("conflict-mine-wrap"),
    conflictMine: $("conflict-mine"),
    preview: $("preview")
  };

  var state = {
    id: null,          // selected note id, null = create mode
    revision: null,
    baseTitle: "",
    baseBody: "",
    busy: false,
    query: "",
    listSeq: 0,
    conflictCurrent: null,
    mineKept: false
  };

  /* ---------- helpers ---------- */

  function cpLength(s) {
    var n = 0;
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i);
      if (c >= 0xd800 && c <= 0xdbff && i + 1 < s.length) { i++; }
      n++;
    }
    return n;
  }

  function isDirty() {
    return els.title.value !== state.baseTitle || els.body.value !== state.baseBody;
  }

  function setStatus(text, isError) {
    els.status.textContent = text;
    els.status.classList.toggle("is-error", !!isError);
  }

  function request(method, path, payload) {
    var opts = { method: method, headers: { "Accept": "application/json" }, cache: "no-store" };
    if (payload !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(payload);
    }
    return fetch(API + path, opts).then(function (resp) {
      return resp.text().then(function (text) {
        var data;
        try { data = JSON.parse(text); } catch (e) { throw new Error("non-json"); }
        return { status: resp.status, ok: resp.ok, data: data };
      });
    });
  }

  function errorMessage(res) {
    var e = res && res.data && res.data.error;
    return e && typeof e.message === "string" ? e.message : "The server rejected the request.";
  }

  var NET_MSG = "Could not reach the server. Your text is still in the editor — try Save again.";

  /* ---------- list ---------- */

  function renderList(notes, total, q) {
    els.list.textContent = "";
    var empty = notes.length === 0;
    els.listState.hidden = !empty;
    if (empty) {
      els.listState.textContent = q
        ? "No notes match “" + q + "”."
        : "No notes yet. Create one with New note, or load the sample note.";
    }
    notes.forEach(function (n) {
      var li = document.createElement("li");
      var b = document.createElement("button");
      b.type = "button";
      b.dataset.id = String(n.id);
      if (n.id === state.id) { b.setAttribute("aria-current", "true"); }
      var t = document.createElement("span");
      t.className = "note-title";
      t.textContent = n.title;
      b.appendChild(t);
      if (n.snippet) {
        var s = document.createElement("span");
        s.className = "note-snippet";
        s.textContent = n.snippet;
        s.setAttribute("aria-hidden", "true");
        b.appendChild(s);
      }
      b.addEventListener("click", function () { selectNote(n.id); });
      li.appendChild(b);
      els.list.appendChild(li);
    });
  }

  function showListMessage(text) {
    els.list.textContent = "";
    els.listState.hidden = false;
    els.listState.textContent = text;
  }

  function loadList() {
    var seq = ++state.listSeq;
    var q = els.search.value.trim();
    state.query = q;
    var path = "/notes" + (q ? "?q=" + encodeURIComponent(q) : "");
    if (!els.list.children.length) { showListMessage("Loading notes…"); }
    return request("GET", path).then(function (res) {
      if (seq !== state.listSeq) { return; }
      if (!res.ok) {
        showListMessage("Could not load notes: " + errorMessage(res));
        return;
      }
      renderList(res.data.notes || [], res.data.total || 0, q);
    }).catch(function () {
      if (seq !== state.listSeq) { return; }
      showListMessage("Could not reach the server. Notes could not be loaded.");
    });
  }

  function markSelected() {
    var items = els.list.querySelectorAll("button");
    for (var i = 0; i < items.length; i++) {
      if (state.id !== null && items[i].dataset.id === String(state.id)) {
        items[i].setAttribute("aria-current", "true");
      } else {
        items[i].removeAttribute("aria-current");
      }
    }
  }

  /* ---------- editor ---------- */

  function updatePreview() { els.preview.textContent = els.body.value; }

  var countTimer = null;
  var lastOver = false;

  function updateCount(immediate) {
    var n = cpLength(els.body.value);
    var over = n > MAX_BODY;
    var write = function () {
      els.count.textContent = n + " / " + MAX_BODY + (over ? " — too long, shorten the text to save" : "");
      els.count.classList.toggle("is-over", over);
    };
    clearTimeout(countTimer);
    if (immediate || over !== lastOver) { write(); } else { countTimer = setTimeout(write, 500); }
    lastOver = over;
    refreshSave();
  }

  function refreshSave() {
    els.save.disabled = state.busy || cpLength(els.body.value) > MAX_BODY;
  }

  function clearTitleError() {
    els.titleError.hidden = true;
    els.titleError.textContent = "";
    els.title.removeAttribute("aria-invalid");
  }

  function hideConflict() {
    state.conflictCurrent = null;
    state.mineKept = false;
    els.conflict.hidden = true;
    els.conflictMineWrap.hidden = true;
    els.conflictActions.hidden = false;
    els.conflictMine.value = "";
  }

  function setEditor(note) {
    if (note) {
      state.id = note.id;
      state.revision = note.revision;
      state.baseTitle = note.title;
      state.baseBody = note.body;
      els.title.value = note.title;
      els.body.value = note.body;
      if (window.location.hash !== "#note-" + note.id) {
        history.replaceState(null, "", "#note-" + note.id);
      }
    } else {
      state.id = null;
      state.revision = null;
      state.baseTitle = "";
      state.baseBody = "";
      els.title.value = "";
      els.body.value = "";
      history.replaceState(null, "", window.location.pathname + window.location.search);
    }
    clearTitleError();
    updatePreview();
    updateCount(true);
    markSelected();
  }

  function confirmDiscard() {
    return !isDirty() || window.confirm("Discard your unsaved changes?");
  }

  function selectNote(id) {
    if (id === state.id && !isDirty()) { return Promise.resolve(); }
    if (!confirmDiscard()) { return Promise.resolve(); }
    setStatus("Loading note…", false);
    return request("GET", "/notes/" + id).then(function (res) {
      if (!res.ok) {
        setStatus("Could not open note: " + errorMessage(res), true);
        return;
      }
      hideConflict();
      setEditor(res.data);
      setStatus("Opened “" + res.data.title + "” (revision " + res.data.revision + ").", false);
    }).catch(function () {
      setStatus("Could not reach the server. The note could not be opened.", true);
    });
  }

  function newNote() {
    if (!confirmDiscard()) { return; }
    hideConflict();
    setEditor(null);
    setStatus("New note. Enter a title and text, then Save.", false);
    els.title.focus();
  }

  /* ---------- save ---------- */

  function showConflict(current) {
    state.conflictCurrent = current;
    state.mineKept = false;
    els.conflictMsg.textContent = "This note changed elsewhere (now revision " + current.revision +
      "). Your text is kept below.";
    els.conflictActions.hidden = false;
    els.conflictMineWrap.hidden = true;
    els.conflict.hidden = false;
    setStatus("Not saved: the note has a newer revision.", true);
  }

  function save(forcedBase) {
    if (state.busy) { return Promise.resolve(); }
    var title = els.title.value.trim();
    var body = els.body.value;
    if (!title) {
      els.titleError.textContent = "Enter a title before saving.";
      els.titleError.hidden = false;
      els.title.setAttribute("aria-invalid", "true");
      els.title.focus();
      return Promise.resolve();
    }
    if (cpLength(body) > MAX_BODY) {
      setStatus("The note text is too long to save.", true);
      return Promise.resolve();
    }
    clearTitleError();
    state.busy = true;
    refreshSave();
    setStatus("Saving…", false);

    var creating = state.id === null;
    var req = creating
      ? request("POST", "/notes", { title: title, body: body })
      : request("PUT", "/notes/" + state.id, {
          title: title,
          body: body,
          base_revision: typeof forcedBase === "number" ? forcedBase : state.revision
        });

    return req.then(function (res) {
      if (res.ok) {
        var note = res.data;
        // Keep exactly what the user typed unless it changed while saving.
        var typedTitle = els.title.value, typedBody = els.body.value;
        state.id = note.id;
        state.revision = note.revision;
        state.baseTitle = note.title;
        state.baseBody = note.body;
        if (typedTitle.trim() === note.title && typedBody.replace(/\r\n/g, "\n") === note.body) {
          els.title.value = note.title;
          els.body.value = note.body;
        }
        hideConflict();
        history.replaceState(null, "", "#note-" + note.id);
        setStatus("Saved revision " + note.revision + ".", false);
        updatePreview();
        updateCount(true);
        return loadList();
      }
      if (res.status === 409 && res.data && res.data.error && res.data.error.code === "stale_revision" && res.data.current) {
        showConflict(res.data.current);
        return;
      }
      setStatus("Not saved: " + errorMessage(res), true);
    }).catch(function () {
      setStatus(NET_MSG, true);
    }).then(function () {
      state.busy = false;
      refreshSave();
    });
  }

  function conflictReload() {
    var cur = state.conflictCurrent;
    if (!cur) { return; }
    els.conflictMine.value = els.title.value + "\n\n" + els.body.value;
    els.conflictMineWrap.hidden = false;
    els.conflictActions.hidden = true;
    state.mineKept = true;
    state.conflictCurrent = null;
    els.conflictMsg.textContent = "Loaded the latest revision " + cur.revision +
      ". Your previous text is kept below.";
    setEditor(cur);
    setStatus("Loaded revision " + cur.revision + ". Your previous text is kept in the box above.", false);
    loadList();
    els.conflictMine.focus();
  }

  function conflictOverwrite() {
    var cur = state.conflictCurrent;
    if (!cur) { return; }
    save(cur.revision);
  }

  /* ---------- sample ---------- */

  function loadSample() {
    if (!confirmDiscard()) { return; }
    els.loadSample.disabled = true;
    setStatus("Loading sample note…", false);
    request("POST", "/fixtures", {}).then(function (res) {
      if (!res.ok) {
        setStatus("Could not load the sample: " + errorMessage(res), true);
        return null;
      }
      els.search.value = "";
      return loadList().then(function () {
        return request("GET", "/notes?q=" + encodeURIComponent("Station field notes"));
      }).then(function (r) {
        var found = r.ok && r.data.notes.filter(function (n) { return n.title === "Station field notes"; })[0];
        if (found) {
          // Discard was already confirmed above; selectNote must not prompt again.
          state.baseTitle = els.title.value;
          state.baseBody = els.body.value;
          return selectNote(found.id);
        }
      });
    }).catch(function () {
      setStatus("Could not reach the server. The sample note was not loaded.", true);
    }).then(function () {
      els.loadSample.disabled = false;
    });
  }

  /* ---------- events ---------- */

  var searchTimer = null;
  els.search.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadList, 150);
  });

  els.newNote.addEventListener("click", newNote);
  els.loadSample.addEventListener("click", loadSample);
  els.save.addEventListener("click", function () { save(); });
  els.conflictReload.addEventListener("click", conflictReload);
  els.conflictOverwrite.addEventListener("click", conflictOverwrite);

  els.body.addEventListener("input", function () {
    updatePreview();
    updateCount(false);
    if (state.conflictCurrent) { hideConflict(); }
  });
  els.title.addEventListener("input", function () {
    if (els.title.value.trim()) { clearTitleError(); }
    if (state.conflictCurrent) { hideConflict(); }
  });

  document.addEventListener("keydown", function (ev) {
    if ((ev.ctrlKey || ev.metaKey) && !ev.altKey && (ev.key === "s" || ev.key === "S")) {
      ev.preventDefault();
      save();
    }
  });

  window.addEventListener("beforeunload", function (ev) {
    if (isDirty()) {
      ev.preventDefault();
      ev.returnValue = "";
    }
  });

  /* ---------- init ---------- */

  updatePreview();
  updateCount(true);
  loadList().then(function () {
    var m = /^#note-(\d{1,18})$/.exec(window.location.hash);
    if (m) { selectNote(parseInt(m[1], 10)); }
  });
})();
