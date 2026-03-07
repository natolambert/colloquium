/**
 * Colloquium Presentation Engine
 * 16:9 scaled canvas, keyboard/click/touch navigation, hash routing, fullscreen
 * Slide picker + per-slide footer
 */
class ColloquiumPresentation {
    constructor() {
        this.deck = document.querySelector('.colloquium-deck');
        this.slides = Array.from(document.querySelectorAll('.slide'));
        this.currentIndex = 0;
        this.totalSlides = this.slides.length;

        // Reference dimensions (16:9)
        this.width = 1280;
        this.height = 720;

        if (this.totalSlides === 0) return;

        this.progressBar = document.querySelector('.colloquium-progress-bar');
        this.pickerOpen = false;

        this._scaleDeck();
        window.addEventListener('resize', () => this._scaleDeck());

        this._createPicker();
        this._bindFooter();
        this._bindPresent();
        this._bindKeyboard();
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
    }

    goTo(index) {
        if (index < 0 || index >= this.totalSlides) return;

        this.slides[this.currentIndex].classList.remove('active');
        this.currentIndex = index;
        this.slides[this.currentIndex].classList.add('active');

        if (window.colloquiumFitDisplayMathIn) {
            requestAnimationFrame(() => {
                window.colloquiumFitDisplayMathIn(this.slides[this.currentIndex]);
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
    }

    next() {
        this.goTo(this.currentIndex + 1);
    }

    prev() {
        this.goTo(this.currentIndex - 1);
    }

    first() {
        this.goTo(0);
    }

    last() {
        this.goTo(this.totalSlides - 1);
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

    _createPicker() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'colloquium-picker-overlay';

        const picker = document.createElement('div');
        picker.className = 'colloquium-picker';

        this.pickerItems = [];

        this.slides.forEach((slide, i) => {
            const btn = document.createElement('button');
            btn.className = 'colloquium-picker-item';
            btn.innerHTML =
                '<span class="colloquium-picker-num">' + (i + 1) + '</span>' +
                '<span>' + this._getSlideTitle(slide, i) + '</span>';
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.goTo(i);
                this._closePicker();
            });
            this.pickerItems.push(btn);
            picker.appendChild(btn);
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

    _openPicker() {
        // Highlight current slide
        this.pickerItems.forEach((btn, i) => {
            btn.classList.toggle('current', i === this.currentIndex);
        });
        this.overlay.classList.add('active');
        this.pickerOpen = true;

        // Scroll current item into view
        const current = this.pickerItems[this.currentIndex];
        if (current) {
            current.scrollIntoView({ block: 'center' });
        }
    }

    _closePicker() {
        this.overlay.classList.remove('active');
        this.pickerOpen = false;
    }

    _bindFooter() {
        // The entire right footer zone is the picker trigger.
        document.querySelectorAll('.colloquium-footer-nav').forEach((target) => {
            target.addEventListener('click', (e) => {
                e.stopPropagation();
                if (this.pickerOpen) {
                    this._closePicker();
                } else {
                    this._openPicker();
                }
            });
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
            // Ignore if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.key) {
                case 'ArrowRight':
                case 'ArrowDown':
                case ' ':
                case 'PageDown':
                    e.preventDefault();
                    this.next();
                    break;
                case 'ArrowLeft':
                case 'ArrowUp':
                case 'PageUp':
                    e.preventDefault();
                    this.prev();
                    break;
                case 'Home':
                    e.preventDefault();
                    this.first();
                    break;
                case 'End':
                    e.preventDefault();
                    this.last();
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
        });
    }

    _bindClick() {
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
            if (e.target.closest('a, button, input, textarea, select, .colloquium-footer, .colloquium-picker-overlay, .colloquium-present')) return;

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
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.colloquium = new ColloquiumPresentation();
});
