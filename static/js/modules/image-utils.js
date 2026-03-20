/**
 * 图片工具模块 - 负责渲染态正文图片预览
 */
class ImageUtils {
    constructor() {
        this.galleryInstances = new Map();
        this.initializeLightGallery();
    }

    initializeLightGallery() {
        const initialize = () => this.setupImagePreviews();
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initialize, { once: true });
            return;
        }
        initialize();
    }

    getPreviewContainers() {
        const containers = [];
        const seen = new Set();
        const candidates = [
            document.getElementById('renderView'),
            document.getElementById('shareDocumentViewer'),
            ...document.querySelectorAll('[data-image-preview-scope]'),
        ];

        candidates.forEach((container) => {
            if (!container || seen.has(container)) {
                return;
            }
            seen.add(container);
            containers.push(container);
        });

        return containers;
    }

    getAvailablePlugins() {
        return [window.lgZoom, window.lgRotate, window.lgThumbnail].filter((plugin) => typeof plugin === 'function');
    }

    destroyImagePreview(container) {
        const instance = this.galleryInstances.get(container);
        if (!instance) {
            return;
        }

        instance.destroy();
        this.galleryInstances.delete(container);
    }

    preparePreviewLinks(container) {
        const images = container.querySelectorAll('img');
        if (!images.length) {
            return 0;
        }

        let preparedCount = 0;
        const scopeId = container.dataset.imagePreviewScope || container.id || 'preview';

        images.forEach((img, index) => {
            if (img.closest('.lg-container') || img.closest('[data-no-image-preview]')) {
                return;
            }

            const imageSrc = img.currentSrc || img.src;
            if (!imageSrc) {
                return;
            }

            let anchor = img.closest('a');
            if (!anchor || !container.contains(anchor)) {
                anchor = document.createElement('a');
                anchor.href = imageSrc;
                anchor.className = 'doc-image-link';
                anchor.dataset.subHtml = img.alt || '';
                img.parentNode.insertBefore(anchor, img);
                anchor.appendChild(img);
            } else {
                anchor.classList.add('doc-image-link');
                const href = (anchor.getAttribute('href') || '').trim();
                if (!href || href === '#' || href.startsWith('javascript:')) {
                    anchor.setAttribute('href', imageSrc);
                }
                if (!anchor.dataset.subHtml && img.alt) {
                    anchor.dataset.subHtml = img.alt;
                }
            }

            anchor.dataset.galleryId = `${scopeId}-image-${index}`;
            preparedCount += 1;
        });

        return preparedCount;
    }

    setupImagePreviewForContainer(container) {
        if (!container || typeof window.lightGallery !== 'function') {
            return;
        }

        const preparedCount = this.preparePreviewLinks(container);
        if (!preparedCount) {
            this.destroyImagePreview(container);
            return;
        }

        this.destroyImagePreview(container);

        this.galleryInstances.set(container, window.lightGallery(container, {
            licenseKey: 'GPLv3',
            selector: '.doc-image-link',
            plugins: this.getAvailablePlugins(),
            download: false,
            counter: true,
            actualSize: false,
            showZoomInOutIcons: true,
            enableZoomAfter: 0,
            mobileSettings: { showCloseButton: true },
        }));
    }

    setupImagePreviews() {
        this.getPreviewContainers().forEach((container) => {
            this.setupImagePreviewForContainer(container);
        });
    }

    refreshImagePreview(target) {
        const resolveContainers = () => {
            if (!target) {
                return this.getPreviewContainers();
            }

            if (typeof target === 'string') {
                return Array.from(document.querySelectorAll(target));
            }

            if (target instanceof Element) {
                return [target];
            }

            return [];
        };

        const containers = resolveContainers();
        containers.forEach((container) => {
            this.destroyImagePreview(container);
        });

        if (!containers.length && !target) {
            this.galleryInstances.forEach((instance) => instance.destroy());
            this.galleryInstances.clear();
        }

        setTimeout(() => {
            if (!containers.length && !target) {
                this.setupImagePreviews();
                return;
            }

            containers.forEach((container) => {
                this.setupImagePreviewForContainer(container);
            });
        }, 100);
    }
}

window.imageUtils = new ImageUtils();
