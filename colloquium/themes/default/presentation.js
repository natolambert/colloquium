/**
 * Colloquium Presentation Engine
 * 16:9 scaled canvas, keyboard/click/touch navigation, hash routing, fullscreen
 * Slide picker (grouped by chapter) + per-slide footer
 */
class ColloquiumPresentation {
    constructor() {
        this.deck = document.querySelector('.colloquium-deck');
        this.slides = Array.from(document.querySelectorAll('.slide'));
        this.currentIndex = 0;
        this.totalSlides = this.slides.length;
        this.chapters = this._readChapters();
        this._iframeKeyboardRelayDocuments = new WeakSet();
        this.slideNumberBuffer = '';
        this.slideNumberTimer = null;
        this.slideNumberCommitDelay = 700;

        if (this._isEmbedded()) {
            document.body.classList.add('colloquium-embedded');
        }

        // Fragment state: current revealed fragment index per slide (0 = none)
        this.fragmentStates = this.slides.map(() => 0);
        this.fragmentCounts = this.slides.map(
            s => parseInt(s.getAttribute('data-fragment-count') || '0', 10)
        );

        // Reference dimensions (16:9)
        this.width = 1280;
        this.height = 720;

        // Capture mode — hide UI chrome for headless screenshots
        if (new URLSearchParams(location.search).has('capture')) {
            document.body.classList.add('colloquium-capture');
        }

        if (this.totalSlides === 0) return;

        this.deck.setAttribute('tabindex', '-1');
        this.progressBar = document.querySelector('.colloquium-progress-bar');
        this.pickerTrigger = document.querySelector('.colloquium-picker-trigger');
        this.pickerTriggerCount = this.pickerTrigger
            ? this.pickerTrigger.querySelector('.colloquium-picker-trigger-count')
            : null;
        this.pickerOpen = false;

        this._scaleDeck();
        window.addEventListener('resize', () => this._scaleDeck());

        this._createPicker();
        this._bindFooter();
        this._bindPickerTrigger();
        this._bindPresent();
        this._bindKeyboard();
        this._bindIframes();
        this._bindClick();
        this._bindTouch();
        this._bindHashChange();

        // Navigate to hash or first slide
        const hash = parseInt(location.hash.replace('#', ''), 10);
        if (hash >= 1 && hash <= this.totalSlides) {
            this.goTo(hash - 1);
        } else {
            this.goTo(0);
        }
    }

    _isEmbedded() {
        try {
            return window.self !== window.top;
        } catch (_) {
            return true;
        }
    }

    /**
     * Check each slide for content overflow and add a visual warning.
     * Temporarily shows all slides to measure, then restores.
     */
    _checkOverflow() {
        const origDisplay = this.slides.map(s => s.style.display);
        this.slides.forEach(s => s.style.display = 'flex');

        this.slides.forEach((slide, i) => {
            if (slide.scrollHeight > slide.clientHeight + 2) {
                const warn = document.createElement('div');
                warn.className = 'colloquium-overflow-warn';
                warn.title = `Slide ${i + 1} content overflows`;
                slide.appendChild(warn);
            }
        });

        this.slides.forEach((s, i) => s.style.display = origDisplay[i]);
    }

    /**
     * Scale the 1280x720 deck to fit the viewport while maintaining 16:9 aspect ratio.
     * Centers the deck with black letterbox/pillarbox bars.
     */
    _scaleDeck() {
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const scale = Math.min(vw / this.width, vh / this.height);

        const scaledW = this.width * scale;
        const scaledH = this.height * scale;
        const offsetX = (vw - scaledW) / 2;
        const offsetY = (vh - scaledH) / 2;

        this.deck.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale})`;

        if (window.colloquiumFitCaptionedFiguresIn) {
            requestAnimationFrame(() => {
                window.colloquiumFitCaptionedFiguresIn(this.slides[this.currentIndex]);
            });
        }
    }

    goTo(index, showAllFragments = false) {
        if (index < 0 || index >= this.totalSlides) return;

        // Cancel any pending numeric jump. The numeric commit path clears the
        // buffer before calling goTo, so this is a no-op there; every other
        // navigation path (click, touch, hash, picker, arrows) cancels a stale
        // digit that would otherwise fire later and snap the deck unexpectedly.
        this._clearSlideNumberBuffer();

        this.slides[this.currentIndex].classList.remove('active');
        this.currentIndex = index;
        this.slides[this.currentIndex].classList.add('active');

        // Set fragment state
        if (showAllFragments) {
            this.fragmentStates[index] = this.fragmentCounts[index];
        } else {
            this.fragmentStates[index] = 0;
        }
        this._updateFragments(index);

        if (window.colloquiumFitDisplayMathIn) {
            requestAnimationFrame(() => {
                window.colloquiumFitDisplayMathIn(this.slides[this.currentIndex]);
            });
        }
        if (window.colloquiumFitCaptionedFiguresIn) {
            requestAnimationFrame(() => {
                window.colloquiumFitCaptionedFiguresIn(this.slides[this.currentIndex]);
            });
        }

        // Update hash
        history.replaceState(null, '', '#' + (this.currentIndex + 1));

        // Update progress bar
        if (this.progressBar) {
            const progress = this.totalSlides > 1
                ? (this.currentIndex / (this.totalSlides - 1)) * 100
                : 100;
            this.progressBar.style.width = progress + '%';
        }

        this._updatePickerTrigger();
        if (this.pickerOpen) this._syncPicker();
    }

    next() {
        // Fragment steps bypass goTo, so cancel any pending numeric jump here
        // too (click/swipe advancing a fragment must not let a stale digit fire).
        this._clearSlideNumberBuffer();
        const fc = this.fragmentCounts[this.currentIndex];
        const fs = this.fragmentStates[this.currentIndex];
        if (fc > 0 && fs < fc) {
            this.fragmentStates[this.currentIndex] = fs + 1;
            this._updateFragments(this.currentIndex);
        } else {
            this.goTo(this.currentIndex + 1);
        }
    }

    prev() {
        this._clearSlideNumberBuffer();
        const fs = this.fragmentStates[this.currentIndex];
        if (fs > 0) {
            this.fragmentStates[this.currentIndex] = fs - 1;
            this._updateFragments(this.currentIndex);
        } else {
            this.goTo(this.currentIndex - 1, true);
        }
    }

    // Jump-style navigation lands with all fragments revealed: jumping means
    // skimming or referencing finished content, not presenting the build-up.
    // Only Right/Left (next/prev) step through fragments.
    nextSlide() {
        this.goTo(this.currentIndex + 1, true);
    }

    prevSlide() {
        this.goTo(this.currentIndex - 1, true);
    }

    first() {
        this.goTo(0);
    }

    last() {
        this.goTo(this.totalSlides - 1, true);
    }

    // --- Numeric Slide Jump ---

    _handleSlideNumberKey(e) {
        if (e.metaKey || e.ctrlKey || e.altKey) return false;

        if (/^\d$/.test(e.key)) {
            e.preventDefault();
            this._appendSlideNumberDigit(e.key);
            return true;
        }

        if (!this.slideNumberBuffer) return false;

        if (e.key === 'Enter') {
            e.preventDefault();
            this._commitSlideNumberBuffer();
            return true;
        }

        if (e.key === 'Backspace') {
            e.preventDefault();
            this._removeSlideNumberDigit();
            return true;
        }

        if (e.key === 'Escape') {
            e.preventDefault();
            this._clearSlideNumberBuffer();
            return true;
        }

        this._clearSlideNumberBuffer();
        return false;
    }

    _appendSlideNumberDigit(digit) {
        this.slideNumberBuffer += digit;
        clearTimeout(this.slideNumberTimer);

        const maxDigits = String(this.totalSlides).length;
        if (this.slideNumberBuffer.length >= maxDigits) {
            this._commitSlideNumberBuffer();
            return;
        }

        this.slideNumberTimer = setTimeout(() => {
            this._commitSlideNumberBuffer();
        }, this.slideNumberCommitDelay);
    }

    _removeSlideNumberDigit() {
        this.slideNumberBuffer = this.slideNumberBuffer.slice(0, -1);
        clearTimeout(this.slideNumberTimer);

        if (this.slideNumberBuffer) {
            this.slideNumberTimer = setTimeout(() => {
                this._commitSlideNumberBuffer();
            }, this.slideNumberCommitDelay);
        }
    }

    _commitSlideNumberBuffer() {
        if (!this.slideNumberBuffer) return;

        const slideNumber = parseInt(this.slideNumberBuffer, 10);
        this._clearSlideNumberBuffer();

        if (slideNumber >= 1 && slideNumber <= this.totalSlides) {
            if (this.pickerOpen) this._closePicker();
            this.goTo(slideNumber - 1, true);
        } else {
            this._showToast('No slide ' + slideNumber);
        }
    }

    _clearSlideNumberBuffer() {
        this.slideNumberBuffer = '';
        clearTimeout(this.slideNumberTimer);
        this.slideNumberTimer = null;
    }

    // --- Fragment Management ---

    _updateFragments(slideIndex) {
        const slide = this.slides[slideIndex];
        const currentStep = this.fragmentStates[slideIndex];
        const fragments = slide.querySelectorAll('[data-fragment-index]');
        fragments.forEach(el => {
            const idx = parseInt(el.getAttribute('data-fragment-index'), 10);
            el.classList.toggle('visible', idx <= currentStep);
        });
    }

    // --- Slide Picker ---

    _getSlideTitle(slide, i) {
        const h1 = slide.querySelector('h1');
        if (h1) return h1.textContent;
        const h2 = slide.querySelector('h2');
        if (h2) return h2.textContent;
        const img = slide.querySelector('img[alt]');
        if (img && img.alt) return img.alt;
        const text = slide.textContent.trim();
        if (text) return text.substring(0, 50) + (text.length > 50 ? '…' : '');
        return 'Slide ' + (i + 1);
    }

    // --- Chapters ---

    // Chapters come from data-chapter attributes written at build time:
    // [{ title, start, end }] with inclusive 0-based slide indices.
    _readChapters() {
        const chapters = [];
        this.slides.forEach((slide, i) => {
            const chapterIndex = this._chapterOf(slide);
            if (chapterIndex < 0) return;
            if (!chapters[chapterIndex]) {
                chapters[chapterIndex] = {
                    title: slide.getAttribute('data-chapter-title') || this._getSlideTitle(slide, i),
                    start: i,
                    end: i,
                };
            }
            chapters[chapterIndex].end = i;
        });
        return chapters;
    }

    _chapterOf(slide) {
        const value = slide.getAttribute('data-chapter');
        return value === null ? -1 : parseInt(value, 10);
    }

    _createPicker() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'colloquium-picker-overlay';

        const picker = document.createElement('div');
        picker.className = 'colloquium-picker';

        this.pickerItems = [];
        this.pickerChapters = [];

        this.slides.forEach((slide, i) => {
            const btn = document.createElement('button');
            btn.className = 'colloquium-picker-item';
            btn.innerHTML =
                '<span class="colloquium-picker-num">' + (i + 1) + '</span>' +
                '<span class="colloquium-picker-title">' + this._getSlideTitle(slide, i) + '</span>';
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.goTo(i, true);
                this._closePicker();
            });
            this.pickerItems.push(btn);

            const chapterIndex = this._chapterOf(slide);
            if (chapterIndex < 0) {
                picker.appendChild(btn);
                return;
            }
            if (!this.pickerChapters[chapterIndex]) {
                this.pickerChapters[chapterIndex] = this._createPickerChapter(chapterIndex);
                picker.appendChild(this.pickerChapters[chapterIndex].group);
            }
            this.pickerChapters[chapterIndex].list.appendChild(btn);
        });

        this.overlay.appendChild(picker);
        document.body.appendChild(this.overlay);

        // Close on click outside the picker card
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) {
                this._closePicker();
            }
        });
    }

    _createPickerChapter(chapterIndex) {
        const chapter = this.chapters[chapterIndex];
        const group = document.createElement('div');
        group.className = 'colloquium-picker-chapter';

        const header = document.createElement('button');
        header.className = 'colloquium-picker-chapter-header';
        header.setAttribute('aria-expanded', 'false');

        const toggle = document.createElement('span');
        toggle.className = 'colloquium-picker-chapter-toggle';
        toggle.setAttribute('aria-hidden', 'true');
        const title = document.createElement('span');
        title.className = 'colloquium-picker-title';
        title.textContent = chapter.title;
        const range = document.createElement('span');
        range.className = 'colloquium-picker-chapter-range';
        range.textContent = chapter.start === chapter.end
            ? String(chapter.start + 1)
            : (chapter.start + 1) + '–' + (chapter.end + 1);
        header.append(toggle, title, range);

        const list = document.createElement('div');
        list.className = 'colloquium-picker-chapter-slides';

        header.addEventListener('click', (e) => {
            e.stopPropagation();
            this._setPickerChapterExpanded(chapterIndex, !group.classList.contains('expanded'));
        });

        group.append(header, list);
        return { group, header, list };
    }

    _setPickerChapterExpanded(chapterIndex, expanded) {
        const entry = this.pickerChapters[chapterIndex];
        if (!entry) return;
        entry.group.classList.toggle('expanded', expanded);
        entry.header.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    }

    _openPicker() {
        // Opening the picker cancels a pending numeric jump — otherwise the
        // stale timer fires mid-browse, closing the picker and jumping away.
        this._clearSlideNumberBuffer();

        this.overlay.classList.add('active');
        this.pickerOpen = true;
        this._syncPicker();
    }

    // Highlight the current slide, expand only its chapter, and scroll it into
    // view. Runs on open and after every navigation while the picker is open,
    // since keyboard navigation stays live behind it.
    _syncPicker() {
        this.pickerItems.forEach((btn, i) => {
            btn.classList.toggle('current', i === this.currentIndex);
        });

        const currentChapter = this._chapterOf(this.slides[this.currentIndex]);
        this.pickerChapters.forEach((entry, chapterIndex) => {
            this._setPickerChapterExpanded(chapterIndex, chapterIndex === currentChapter);
            entry.header.classList.toggle('current', chapterIndex === currentChapter);
        });

        const current = this.pickerItems[this.currentIndex];
        if (current) {
            current.scrollIntoView({ block: 'center' });
        }
    }

    _closePicker() {
        // Dismissing the picker also cancels a pending numeric jump (the
        // commit path clears its buffer before closing, so this is a no-op
        // there).
        this._clearSlideNumberBuffer();
        this.overlay.classList.remove('active');
        this.pickerOpen = false;
    }

    _togglePicker() {
        if (this.pickerOpen) {
            this._closePicker();
        } else {
            this._openPicker();
        }
    }

    _updatePickerTrigger() {
        if (!this.pickerTriggerCount) return;
        this.pickerTriggerCount.textContent = (this.currentIndex + 1) + ' / ' + this.totalSlides;
    }

    _bindFooter() {
        // The entire right footer zone is the picker trigger.
        document.querySelectorAll('.colloquium-footer-nav').forEach((target) => {
            target.addEventListener('click', (e) => {
                e.stopPropagation();
                this._togglePicker();
            });
        });
    }

    _bindPickerTrigger() {
        if (!this.pickerTrigger) return;
        this.pickerTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            this._togglePicker();
        });
    }

    _bindPresent() {
        const btn = document.querySelector('.colloquium-present');
        if (btn) {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this._toggleFullscreen();
            });
        }
    }

    // --- Navigation Bindings ---

    _bindKeyboard() {
        document.addEventListener('keydown', (e) => {
            if (this._isTextInputTarget(e.target)) return;
            this._handleNavigationKey(e);
        });
    }

    _isTextInputTarget(target) {
        if (!target || !target.tagName) return false;
        if (target.isContentEditable) return true;
        return ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
    }

    _handleNavigationKey(e) {
        if (this._handleSlideNumberKey(e)) return;

        switch (e.key) {
            // Left/Right (and Space/PageDown) step through fragments then
            // slides — the familiar PowerPoint/Keynote "advance" axis.
            case 'ArrowRight':
            case ' ':
            case 'PageDown':
                e.preventDefault();
                this.next();
                break;
            case 'ArrowLeft':
            case 'PageUp':
                e.preventDefault();
                this.prev();
                break;
            // Up/Down jump whole slides, skipping fragments — a fast axis for
            // moving past fragment-heavy slides.
            case 'ArrowDown':
                e.preventDefault();
                this.nextSlide();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.prevSlide();
                break;
            case 'Home':
                e.preventDefault();
                this.first();
                break;
            case 'End':
                e.preventDefault();
                this.last();
                break;
            case 'c':
            case 'C':
                // Plain 'c' copies the current slide's markdown source.
                // Leave Cmd/Ctrl+C alone so the browser can copy selected text.
                if (e.metaKey || e.ctrlKey || e.altKey) return;
                e.preventDefault();
                this._copyCurrentSlideMarkdown();
                break;
            case 'f':
            case 'F':
                e.preventDefault();
                this._toggleFullscreen();
                break;
            case 'Escape':
                if (this.pickerOpen) {
                    this._closePicker();
                } else if (document.fullscreenElement) {
                    document.exitFullscreen();
                }
                break;
        }
    }

    _bindIframes() {
        document.querySelectorAll('iframe.colloquium-iframe').forEach((iframe) => {
            this._bindIframeKeyboardRelay(iframe);
            iframe.addEventListener('load', () => this._bindIframeKeyboardRelay(iframe));
            iframe.addEventListener('focus', () => this._recoverFocusFromIframe(iframe));
        });
    }

    _bindIframeKeyboardRelay(iframe) {
        if (iframe.dataset.colloquiumPreserveKeyboard === 'false') return false;

        try {
            const iframeDocument = iframe.contentWindow && iframe.contentWindow.document;
            if (!iframeDocument) return false;
            if (this._iframeKeyboardRelayDocuments.has(iframeDocument)) return true;

            iframeDocument.addEventListener('keydown', (e) => {
                if (this._isTextInputTarget(e.target)) return;
                this._handleNavigationKey(e);
            });
            this._iframeKeyboardRelayDocuments.add(iframeDocument);
            return true;
        } catch (_) {
            // Cross-origin frames cannot expose their keyboard events to the parent deck.
            return false;
        }
    }

    _recoverFocusFromIframe(iframe) {
        if (iframe.dataset.colloquiumPreserveKeyboard === 'false') return;
        if (this._bindIframeKeyboardRelay(iframe)) return;

        setTimeout(() => {
            if (document.activeElement === iframe) {
                iframe.blur();
                window.focus();
                this.deck.focus({ preventScroll: true });
            }
        }, 0);
    }

    _bindClick() {
        // Track the pointer-down position so we can tell a click from a drag.
        // A drag (mouse moved between down and up) means the user was selecting
        // text or otherwise interacting, not trying to advance the slide.
        let downX = 0;
        let downY = 0;
        const DRAG_THRESHOLD = 8; // px of movement that counts as a drag, not a click
        document.addEventListener('mousedown', (e) => {
            downX = e.clientX;
            downY = e.clientY;
        });

        document.addEventListener('click', (e) => {
            // Handle citation links — navigate to the slide containing the target ref
            const citeLink = e.target.closest('a.colloquium-cite');
            if (citeLink) {
                e.preventDefault();
                e.stopPropagation();
                const href = citeLink.getAttribute('href');
                if (href && href.startsWith('#')) {
                    const target = document.getElementById(href.slice(1));
                    if (target) {
                        const slide = target.closest('.slide');
                        if (slide) {
                            const idx = this.slides.indexOf(slide);
                            if (idx >= 0) this.goTo(idx);
                        }
                    }
                }
                return;
            }

            // Ignore clicks on links, interactive elements, footer, and picker
            if (e.target.closest('a, button, input, textarea, select, .colloquium-footer, .colloquium-picker-overlay, .colloquium-present, .colloquium-picker-trigger')) return;

            // Don't navigate if the user is highlighting/copying text. A drag
            // (pointer moved between down and up) or a live text selection both
            // mean "select", not "next slide".
            const dragDistance = Math.hypot(e.clientX - downX, e.clientY - downY);
            if (dragDistance > DRAG_THRESHOLD) return;
            // A multi-click (double/triple) is a word/paragraph selection gesture,
            // not navigation. This catches the later clicks of a multi-click; the
            // very first click can't be distinguished without deferring all
            // navigation, which we avoid so slide clicks stay snappy.
            if (e.detail > 1) return;
            const selection = window.getSelection();
            if (selection && !selection.isCollapsed && selection.toString().trim()) return;

            const x = e.clientX / window.innerWidth;
            if (x < 0.33) {
                this.prev();
            } else {
                this.next();
            }
        });
    }

    _bindTouch() {
        let startX = 0;
        let startY = 0;

        document.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
        }, { passive: true });

        document.addEventListener('touchend', (e) => {
            const dx = e.changedTouches[0].clientX - startX;
            const dy = e.changedTouches[0].clientY - startY;

            // Only trigger on horizontal swipes (more horizontal than vertical, min 50px)
            if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
                if (dx < 0) {
                    this.next();
                } else {
                    this.prev();
                }
            }
        }, { passive: true });
    }

    _bindHashChange() {
        window.addEventListener('hashchange', () => {
            const hash = parseInt(location.hash.replace('#', ''), 10);
            if (hash >= 1 && hash <= this.totalSlides && hash - 1 !== this.currentIndex) {
                this.goTo(hash - 1);
            }
        });
    }

    _toggleFullscreen() {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            document.documentElement.requestFullscreen().catch(() => {});
        }
    }

    // --- Copy slide as markdown ---

    _decodeMarkdown(b64) {
        // base64 (UTF-8) → string, so unicode math/symbols round-trip cleanly.
        const binary = atob(b64);
        const bytes = Uint8Array.from(binary, c => c.charCodeAt(0));
        return new TextDecoder().decode(bytes);
    }

    _copyCurrentSlideMarkdown() {
        const slide = this.slides[this.currentIndex];
        const encoded = slide && slide.getAttribute('data-colloquium-md');
        if (!encoded) {
            this._showToast('No markdown source for this slide');
            return;
        }
        let markdown;
        try {
            markdown = this._decodeMarkdown(encoded);
        } catch (_) {
            this._showToast('Could not read slide markdown');
            return;
        }
        const done = () => this._showToast('Copied slide markdown');
        const fail = () => this._showToast('Copy failed — clipboard blocked');
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(markdown).then(done, () => {
                if (!this._copyViaTextarea(markdown)) fail();
                else done();
            });
        } else if (this._copyViaTextarea(markdown)) {
            done();
        } else {
            fail();
        }
    }

    _copyViaTextarea(text) {
        // Fallback for insecure contexts (file://, plain http) where the async
        // Clipboard API is unavailable.
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.top = '-1000px';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        let ok = false;
        try {
            ok = document.execCommand('copy');
        } catch (_) {
            ok = false;
        }
        document.body.removeChild(ta);
        return ok;
    }

    _showToast(message) {
        if (!this._toast) {
            this._toast = document.createElement('div');
            this._toast.className = 'colloquium-toast';
            document.body.appendChild(this._toast);
        }
        this._toast.textContent = message;
        this._toast.classList.add('visible');
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => {
            this._toast.classList.remove('visible');
        }, 1500);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.colloquium = new ColloquiumPresentation();
});
