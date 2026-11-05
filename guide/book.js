/* Copy buttons, line breaking that keeps names whole, card tables at phone width, and the chapter
   list's scroll. Every page reads the same without it: commands stay selectable text, code scrolls
   inside its box, and tables keep their columns. */
(function () {
  /* A head's words go in one span, so markup inside them (a path in code) stays one flex item
     beside the Copy button. */
  function wrapLabel(head) {
    if (head.querySelector(".head-label")) return;
    var span = document.createElement("span");
    span.className = "head-label";
    while (head.firstChild) span.appendChild(head.firstChild);
    head.appendChild(span);
  }
  function addCopy(block) {
    var head = block.querySelector(".cmd-head, .say-head");
    var pre = block.querySelector("pre.in, .say > pre");
    if (!head) return;
    wrapLabel(head);
    if (!pre || head.querySelector(".copy")) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy";
    btn.textContent = "Copy";
    btn.addEventListener("click", function () {
      var text = pre.innerText.replace(/^\$ /gm, "");
      function done(label) { btn.textContent = label; setTimeout(function () { btn.textContent = "Copy"; }, 1500); }
      try {
        navigator.clipboard.writeText(text).then(function () { done("Copied"); }, function () { select(pre); done("Selected"); });
      } catch (e) { select(pre); done("Selected"); }
    });
    head.appendChild(btn);
  }
  function select(node) {
    try { var r = document.createRange(); r.selectNodeContents(node); var s = window.getSelection(); s.removeAllRanges(); s.addRange(r); } catch (e) {}
  }
  document.querySelectorAll(".cmd, .say").forEach(addCopy);

  /* Line breaks that keep names whole. A browser breaks after any hyphen, so c1-skills, --only and
     p3-tutor would split as if they were hyphenated words. In code and in example text, a line may
     break only at a space, or after a slash, a comma or a #; a piece with a hyphen stays on one line
     unless it is too long to fit a phone's line. */
  var LONGEST_WHOLE = 28;
  function breakText(textNode) {
    var text = textNode.nodeValue;
    if (!/[-\/,#]/.test(text)) return;
    var frag = document.createDocumentFragment();
    text.split(/(\s+)/).forEach(function (token) {
      if (!token) return;
      if (/^\s+$/.test(token)) { frag.appendChild(document.createTextNode(token)); return; }
      var pieces = token.match(/[^\/,#]*[\/,#]|[^\/,#]+$/g) || [token];
      pieces.forEach(function (piece, i) {
        if (i > 0) frag.appendChild(document.createElement("wbr"));
        if (piece.indexOf("-") >= 0 && piece.length <= LONGEST_WHOLE) {
          var span = document.createElement("span");
          span.className = "nw";
          span.textContent = piece;
          frag.appendChild(span);
        } else {
          frag.appendChild(document.createTextNode(piece));
        }
      });
    });
    textNode.parentNode.replaceChild(frag, textNode);
  }
  function keepNamesWhole(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) { return n.parentNode.closest(".nw") ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT; }
    });
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(breakText);
  }
  /* Inline code, example text and the words to say to a window. */
  document.querySelectorAll(":not(pre) > code, pre:not(.in):not(.out):not(.tree)").forEach(keepNamesWhole);

  /* What a command prints wraps like a terminal, and each line's continuation is indented under the
     line's text: under the message after a label such as "Now:" or "  TODO", and otherwise two
     places in. Output whose columns matter is a pre.out.cols, and scrolls instead. */
  var LONGEST_LABEL = 12;
  document.querySelectorAll("pre.out:not(.cols)").forEach(function (pre) {
    var box = pre.querySelector(":scope > code") || pre;
    if (box.querySelector("*")) return;
    var lines = box.textContent.replace(/\n$/, "").split("\n");
    box.textContent = "";
    lines.forEach(function (line) {
      var ln = document.createElement("span");
      ln.className = "ln";
      var label = /^(\s*\S+(?: \S+)?\s{2,})\S/.exec(line);
      var hang = label && label[1].length <= LONGEST_LABEL ? label[1].length : /^\s*/.exec(line)[0].length + 2;
      ln.style.setProperty("--hang", hang + "ch");
      ln.textContent = line || " ";
      keepNamesWhole(ln);
      box.appendChild(ln);
    });
    pre.classList.add("hang");
  });

  /* A table with a column of prose gets its column names on each cell, so at phone width the
     stylesheet can show one card per row. A table of short values keeps its columns and scrolls.
     A page can decide for itself: class="stack" by hand, or class="keep-cols". */
  var captions = 0;
  document.querySelectorAll(".table-wrap table").forEach(function (t) {
    var heads = [].slice.call(t.querySelectorAll("thead th"));
    var rows = [].slice.call(t.querySelectorAll("tbody tr"));
    var labels = heads.map(function (h) { return h.textContent.trim(); });
    function eachCell(fn) {
      rows.forEach(function (tr) {
        var col = 0;
        [].forEach.call(tr.children, function (cell) { fn(cell, col); col += cell.colSpan || 1; });
      });
    }
    if (!t.classList.contains("stack") && !t.classList.contains("keep-cols") && heads.length >= 2 && !t.querySelector("[rowspan]")) {
      var total = [], count = [];
      eachCell(function (cell, col) {
        total[col] = (total[col] || 0) + cell.textContent.trim().length;
        count[col] = (count[col] || 0) + 1;
      });
      var prose = total.some(function (sum, col) { return sum / count[col] >= 25; });
      if (prose) t.classList.add("stack");
    }
    if (t.classList.contains("stack")) {
      eachCell(function (cell, col) { if (labels[col] && !cell.hasAttribute("data-label")) cell.setAttribute("data-label", labels[col]); });
    }
    /* The caption goes under the box, like a figure's, so it never scrolls away with a wide table. */
    var caption = t.querySelector(":scope > caption");
    var wrap = t.closest(".table-wrap");
    if (caption && wrap) {
      var p = document.createElement("p");
      p.className = "table-caption";
      p.id = "table-caption-" + (++captions);
      while (caption.firstChild) p.appendChild(caption.firstChild);
      caption.remove();
      t.setAttribute("aria-labelledby", p.id);
      wrap.after(p);
    }
  });

  /* On a narrow screen the chapter list starts folded, so the chapter itself is the first thing you see. */
  if (window.matchMedia && window.matchMedia("(max-width: 979px)").matches) {
    document.querySelectorAll("details.toc-box").forEach(function (d) { d.removeAttribute("open"); });
  }
  /* On a wide screen the chapter list scrolls inside its box; start it with the current chapter in view. */
  function showCurrent() {
    var list = document.querySelector(".toc-list");
    var current = document.querySelector(".toc-list a.current");
    if (!list || !current || list.scrollHeight <= list.clientHeight) return;
    var top = current.getBoundingClientRect().top - list.getBoundingClientRect().top + list.scrollTop;
    list.scrollTop = Math.max(0, top - list.clientHeight / 2);
  }
  showCurrent();
  /* The web fonts can re-wrap the list after this runs, so place it again once they have loaded. */
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(showCurrent);
})();
