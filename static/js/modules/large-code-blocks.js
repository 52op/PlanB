/**
 * Large Code Blocks Module
 * Handles large code block rendering, expansion, collapse, and copy functionality
 * Can be used across blog pages, documentation pages, and share pages
 */

(function () {
  "use strict";

  const LANGUAGE_LABELS = {
    js: "JavaScript",
    javascript: "JavaScript",
    jsx: "JSX",
    ts: "TypeScript",
    typescript: "TypeScript",
    tsx: "TSX",
    py: "Python",
    python: "Python",
    sh: "Bash",
    shell: "Bash",
    bash: "Bash",
    zsh: "Zsh",
    ps1: "PowerShell",
    powershell: "PowerShell",
    html: "HTML",
    xml: "XML",
    css: "CSS",
    scss: "SCSS",
    sass: "Sass",
    less: "Less",
    json: "JSON",
    yaml: "YAML",
    yml: "YAML",
    md: "Markdown",
    markdown: "Markdown",
    sql: "SQL",
    go: "Go",
    java: "Java",
    kotlin: "Kotlin",
    swift: "Swift",
    php: "PHP",
    ruby: "Ruby",
    rust: "Rust",
    rs: "Rust",
    c: "C",
    cpp: "C++",
    cxx: "C++",
    cc: "C++",
    cs: "C#",
    csharp: "C#",
    vue: "Vue",
    dockerfile: "Dockerfile",
    ini: "INI",
    toml: "TOML",
    plaintext: "Text",
    text: "Text",
    txt: "Text",
  };

  // ==================== Helper Functions ====================

  function ensureCodeBlockWrapper(pre) {
    if (!pre || !pre.parentNode) return null;

    if (
      pre.parentElement &&
      pre.parentElement.classList.contains("code-block-wrapper")
    ) {
      return pre.parentElement;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "code-block-wrapper";
    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(pre);
    return wrapper;
  }

  function detectCodeLanguage(pre) {
    const code = pre.querySelector("code");
    const sources = [];

    if (pre.dataset.language) {
      sources.push(pre.dataset.language);
    }
    if (pre.getAttribute("data-language")) {
      sources.push(pre.getAttribute("data-language"));
    }
    if (code && code.dataset.language) {
      sources.push(code.dataset.language);
    }
    if (code && code.getAttribute("data-language")) {
      sources.push(code.getAttribute("data-language"));
    }
    if (code && code.className) {
      sources.push(code.className);
    }
    if (pre.className) {
      sources.push(pre.className);
    }

    for (let i = 0; i < sources.length; i += 1) {
      const token = extractLanguageToken(sources[i]);
      if (token) {
        return toLanguageLabel(token);
      }
    }

    return "";
  }

  function extractLanguageToken(value) {
    if (!value) return "";

    const source = String(value).trim();
    if (!source) return "";

    const matched = source.match(/\b(?:language|lang)-([a-z0-9_+#.-]+)/i);
    if (matched && matched[1]) {
      return matched[1].toLowerCase();
    }

    const normalized = source
      .toLowerCase()
      .replace(/[^a-z0-9+#.-]+/g, " ")
      .trim()
      .split(/\s+/);
    for (let i = 0; i < normalized.length; i += 1) {
      if (LANGUAGE_LABELS[normalized[i]]) {
        return normalized[i];
      }
    }

    if (normalized.length === 1) {
      return normalized[0];
    }

    return "";
  }

  function toLanguageLabel(token) {
    if (!token) return "";
    if (LANGUAGE_LABELS[token]) {
      return LANGUAGE_LABELS[token];
    }

    if (token.length <= 4) {
      return token.toUpperCase();
    }

    return token.charAt(0).toUpperCase() + token.slice(1);
  }

  function showCopySuccess(button) {
    const copyIcon = button.querySelector(".copy-icon");
    const checkIcon = button.querySelector(".check-icon");
    const copyText = button.querySelector(".copy-text");

    // Show success state
    copyIcon.style.display = "none";
    checkIcon.style.display = "block";
    copyText.textContent = "已复制";
    button.classList.add("copied");

    // Reset after 2 seconds
    setTimeout(function () {
      copyIcon.style.display = "block";
      checkIcon.style.display = "none";
      copyText.textContent = "复制";
      button.classList.remove("copied");
    }, 2000);
  }

  function fallbackCopy(text, button) {
    // Fallback for older browsers
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();

    try {
      document.execCommand("copy");
      showCopySuccess(button);
    } catch (err) {
      console.error("Failed to copy:", err);
      const copyText = button.querySelector(".copy-text");
      copyText.textContent = "复制失败";
      setTimeout(function () {
        copyText.textContent = "复制";
      }, 2000);
    }

    document.body.removeChild(textarea);
  }

  function injectLargeCodePatchStyles() {
    if (document.getElementById("largeCodePatchStyles")) return;
    const style = document.createElement("style");
    style.id = "largeCodePatchStyles";
    style.textContent = `
      .large-code-block {
        position: relative !important;
        background: transparent !important;
        padding: 0 !important;
        border: none !important;
        box-shadow: none !important;
        margin: 1.5em 0 !important;
      }
      .large-code-block .large-code-toolbar {
        display: none !important;
      }
      .large-code-block pre {
        position: relative !important;
        max-height: none !important;
        min-height: 300px !important;
        overflow-x: auto !important;
        overflow-y: hidden !important;
        margin: 0 !important;
      }
      .large-code-block.is-truncated:not(.is-expanded) pre {
        height: min(65vh, 720px) !important;
      }
      .large-code-block.is-expanded pre {
        max-height: none !important;
        height: auto !important;
        overflow-y: visible !important;
      }
      .large-code-block.is-truncated:not(.is-expanded) pre::after {
        content: "" !important;
        position: absolute !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        height: 96px !important;
        pointer-events: none !important;
        background: linear-gradient(to bottom, rgba(15, 23, 42, 0), rgba(15, 23, 42, 0.92)) !important;
      }
      [data-theme="light"] .large-code-block.is-truncated:not(.is-expanded) pre::after,
      :root:not([data-theme="dark"]) .large-code-block.is-truncated:not(.is-expanded) pre::after {
        background: linear-gradient(to bottom, rgba(248, 250, 252, 0), rgba(248, 250, 252, 0.96)) !important;
      }
      .large-code-block .large-code-actions {
        position: absolute !important;
        top: 8px !important;
        right: 8px !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        z-index: 10 !important;
      }
      .large-code-block .code-copy-btn {
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
        padding: 6px 12px !important;
        border-radius: 8px !important;
        border: 1px solid rgba(148, 163, 184, 0.3) !important;
        background: rgba(255, 255, 255, 0.9) !important;
        color: #334155 !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
      }
      [data-theme="dark"] .large-code-block .code-copy-btn {
        background: rgba(30, 41, 59, 0.9) !important;
        color: #e2e8f0 !important;
        border-color: rgba(148, 163, 184, 0.2) !important;
      }
      .large-code-block .code-copy-btn:hover {
        background: rgba(59, 130, 246, 0.9) !important;
        color: white !important;
        border-color: rgba(59, 130, 246, 0.5) !important;
        transform: translateY(-1px) !important;
      }
      .large-code-block .code-copy-btn.copied {
        background: rgba(16, 185, 129, 0.9) !important;
        color: white !important;
        border-color: rgba(16, 185, 129, 0.5) !important;
      }
      .large-code-block .code-copy-btn svg {
        width: 16px !important;
        height: 16px !important;
        flex-shrink: 0 !important;
      }
      .large-code-block .large-code-bottom-actions {
        position: absolute !important;
        bottom: 8px !important;
        right: 8px !important;
        display: none !important;
        z-index: 10 !important;
      }
      .large-code-block.is-expanded .large-code-bottom-actions {
        display: flex !important;
      }
      .large-code-block .large-code-expand-btn {
        opacity: 1 !important;
      }
      .large-code-block .large-code-expand-btn[disabled] {
        opacity: 0.68 !important;
        cursor: not-allowed !important;
      }
      @media (max-width: 768px) {
        .large-code-block.is-truncated:not(.is-expanded) pre {
          height: min(55vh, 520px) !important;
          min-height: 240px !important;
        }
        .large-code-block .large-code-actions {
          gap: 6px !important;
        }
        .large-code-block .code-copy-btn {
          min-width: 36px !important;
          height: 30px !important;
          padding: 0 10px !important;
          opacity: 1 !important;
        }
        .large-code-block .large-code-expand-btn {
          min-width: 72px !important;
        }
        .large-code-block .code-copy-btn .copy-text {
          display: inline !important;
          white-space: nowrap !important;
          font-size: 11px !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  // ==================== Main Initialization Function ====================

  function initLargeCodeBlocks(options) {
    const config = Object.assign(
      {
        context: "blog", // 'blog' | 'docs' | 'share'
        showMetadata: false,
        compactMode: false,
      },
      options || {}
    );

    const blocks = document.querySelectorAll(".large-code-block");
    if (!blocks.length) return;

    injectLargeCodePatchStyles();

    blocks.forEach(function (block) {
      const pre = block.querySelector("pre");
      const code = pre ? pre.querySelector("code") : null;
      if (!pre || !code) return;

      if (block.dataset.largeCodePatched !== "true") {
        block.style.overflow = "visible";
        pre.style.maxHeight = "none";
        pre.style.overflowX = "auto";
        pre.style.overflowY = "hidden";
        pre.style.overscrollBehavior = "auto";
        code.style.display = "block";
        code.style.whiteSpace = "pre";
        code.style.overflow = "visible";
        block.dataset.largeCodePatched = "true";
      }

      if (!pre.querySelector(".large-code-actions")) {
        const actions = document.createElement("div");
        actions.className = "large-code-actions";

        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "code-copy-btn";
        copyBtn.title = "复制代码";
        copyBtn.innerHTML = `
          <svg class="copy-icon" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
          </svg>
          <svg class="check-icon" width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display: none;">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
          </svg>
          <span class="copy-text">复制</span>
        `;
        copyBtn.addEventListener("click", function () {
          const text = code.textContent || "";
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard
              .writeText(text)
              .then(function () {
                showCopySuccess(copyBtn);
              })
              .catch(function () {
                fallbackCopy(text, copyBtn);
              });
          } else {
            fallbackCopy(text, copyBtn);
          }
        });

        const expandBtn = document.createElement("button");
        expandBtn.type = "button";
        expandBtn.className = "code-copy-btn large-code-expand-btn";
        expandBtn.title = "展开全文";
        expandBtn.innerHTML = `
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
          </svg>
          <span class="copy-text">展开</span>
        `;

        const updateBlockViewState = function (shouldScroll) {
          const isExpanded = block.classList.contains("is-expanded");
          const textNode = expandBtn.querySelector(".copy-text");
          const iconSvg = expandBtn.querySelector("svg");
          if (!textNode) return;
          
          if (isExpanded) {
            textNode.textContent = "收起";
            expandBtn.title = "收起代码";
            if (iconSvg) {
              iconSvg.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"></path>';
            }
          } else {
            textNode.textContent = "展开";
            expandBtn.title = "展开全文";
            if (iconSvg) {
              iconSvg.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>';
            }
          }
          
          if (isExpanded) {
            pre.style.overflowY = "visible";
          } else {
            pre.style.overflowY = "hidden";
            pre.scrollTop = 0;
            // Only scroll into view when explicitly requested (e.g., when user clicks collapse)
            if (shouldScroll === true && typeof block.scrollIntoView === "function") {
              block.scrollIntoView({ behavior: "smooth", block: "start" });
            }
          }
        };

        const collapseBottomBtn = document.createElement("button");
        collapseBottomBtn.type = "button";
        collapseBottomBtn.className =
          "code-copy-btn large-code-collapse-bottom-btn";
        collapseBottomBtn.title = "收起代码";
        collapseBottomBtn.innerHTML = `
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"></path>
          </svg>
          <span class="copy-text">收起</span>
        `;
        collapseBottomBtn.addEventListener("click", function () {
          block.classList.remove("is-expanded");
          updateBlockViewState(true); // Pass true to enable scrolling when user clicks collapse
        });

        if (!pre.querySelector(".large-code-bottom-actions")) {
          const bottomActions = document.createElement("div");
          bottomActions.className = "large-code-bottom-actions";
          bottomActions.appendChild(collapseBottomBtn);
          pre.appendChild(bottomActions);
        }

        expandBtn.addEventListener("click", function () {
          if (block.dataset.fullLoaded === "true") {
            block.classList.toggle("is-expanded");
            updateBlockViewState(false); // Don't scroll when toggling
            return;
          }

          const sourceFile = block.dataset.sourceFile || "";
          const blockIndex = block.dataset.codeBlockIndex || "";
          if (!sourceFile || !blockIndex) {
            expandBtn.disabled = true;
            expandBtn.querySelector(".copy-text").textContent = "不可展开";
            return;
          }

          expandBtn.disabled = true;
          expandBtn.querySelector(".copy-text").textContent = "加载中...";

          const url =
            "/api/code_block_full?filename=" +
            encodeURIComponent(sourceFile) +
            "&block_index=" +
            encodeURIComponent(blockIndex);

          fetch(url, { credentials: "same-origin" })
            .then(function (res) {
              if (!res.ok) throw new Error("请求失败");
              return res.json();
            })
            .then(function (data) {
              if (!data || typeof data.content !== "string") {
                throw new Error("数据无效");
              }
              code.textContent = data.content;
              block.dataset.fullLoaded = "true";
              block.classList.add("is-expanded");
              updateBlockViewState(false); // Don't scroll when expanding
            })
            .catch(function () {
              expandBtn.disabled = false;
              expandBtn.querySelector(".copy-text").textContent = "重试展开";
            })
            .finally(function () {
              if (block.dataset.fullLoaded === "true") {
                expandBtn.disabled = false;
              }
            });
        });

        updateBlockViewState(false); // Initial state update without scrolling

        actions.appendChild(copyBtn);
        actions.appendChild(expandBtn);
        pre.appendChild(actions);
      }
    });
  }

  // Export to global scope
  window.initLargeCodeBlocks = initLargeCodeBlocks;
})();
