/**
 * Colloquium Presentation Engine
 * 16:9 scaled canvas, keyboard/click/touch navigation, hash routing, fullscreen
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

        this.counter = document.querySelector('.colloquium-counter');
        this.progressBar = document.querySelector('.colloquium-progress-bar');

        this._scaleDeck();
        window.addEventListener('resize', () => this._scaleDeck());

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

        // Update hash
        history.replaceState(null, '', '#' + (this.currentIndex + 1));

        // Update counter
        if (this.counter) {
            this.counter.textContent = (this.currentIndex + 1) + ' / ' + this.totalSlides;
        }

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
                    if (document.fullscreenElement) {
                        document.exitFullscreen();
                    }
                    break;
            }
        });
    }

    _bindClick() {
        document.addEventListener('click', (e) => {
            // Ignore clicks on links or interactive elements
            if (e.target.closest('a, button, input, textarea, select')) return;

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
