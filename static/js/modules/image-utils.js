/**
 * 图片工具模块 - 负责文档渲染态图片预览
 */
class ImageUtils {
    constructor() {
        this.lightGalleryInstance = null;
        this.initializeLightGallery();
    }

    initializeLightGallery() {
        const initialize = () => this.setupDocumentImagePreview();
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initialize, { once: true });
            return;
        }
        initialize();
    }

    setupDocumentImagePreview() {
        const renderView = document.getElementById('renderView');
        const renderImages = renderView ? renderView.querySelectorAll('img') : [];
        if (!renderView || !renderImages.length || typeof window.lightGallery !== 'function') {
            return;
        }

        renderImages.forEach((img, index) => {
            if (img.closest('.lg-container')) return;

            let anchor = img.parentElement;
            if (!anchor || anchor.tagName !== 'A') {
                anchor = document.createElement('a');
                anchor.href = img.currentSrc || img.src;
                anchor.className = 'doc-image-link';
                anchor.dataset.subHtml = img.alt || '';
                img.parentNode.insertBefore(anchor, img);
                anchor.appendChild(img);
            } else {
                anchor.classList.add('doc-image-link');
                if (!anchor.getAttribute('href')) {
                    anchor.setAttribute('href', img.currentSrc || img.src);
                }
            }

            anchor.dataset.galleryId = `doc-image-${index}`;
        });

        if (this.lightGalleryInstance) {
            this.lightGalleryInstance.destroy();
        }

        this.lightGalleryInstance = window.lightGallery(renderView, {
            licenseKey: 'GPLv3',
            selector: '.doc-image-link',
            plugins: [window.lgZoom, window.lgRotate, window.lgThumbnail],
            download: false,
            counter: true,
            mobileSettings: { showCloseButton: true },
        });
    }

    refreshImagePreview() {
        if (this.lightGalleryInstance) {
            this.lightGalleryInstance.destroy();
            this.lightGalleryInstance = null;
        }

        setTimeout(() => {
            this.setupDocumentImagePreview();
        }, 100);
    }
}

window.imageUtils = new ImageUtils();
