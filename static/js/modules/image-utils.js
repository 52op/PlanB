/**
 * 图片工具模块 - 处理图片预览、尺寸调整等功能
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

    buildSizedImageMarkup(url, altText = 'Image') {
        return new Promise((resolve) => {
            // 创建临时图片元素获取尺寸
            const tempImg = new Image();

            tempImg.onload = () => {
                const width = tempImg.naturalWidth;
                const height = tempImg.naturalHeight;

                // 如果图片较大，提供尺寸选择
                if (width > 800 || height > 600) {
                    this.showImageSizeDialog(url, altText, width, height)
                        .then(result => resolve(result));
                } else {
                    resolve({ cancelled: true });
                }
            };

            tempImg.onerror = () => {
                resolve({ cancelled: true });
            };

            tempImg.src = url;
        });
    }

    showImageSizeDialog(url, altText, originalWidth, originalHeight) {
        return new Promise((resolve) => {
            const dialog = document.createElement('div');
            dialog.className = 'modal-overlay';
            dialog.innerHTML = `
                <div class="modal-content" style="max-width: 500px;">
                    <h3>选择图片尺寸</h3>
                    <p>原始尺寸: ${originalWidth} × ${originalHeight}</p>
                    <div style="margin: 20px 0;">
                        <label style="display: block; margin-bottom: 10px;">
                            <input type="radio" name="imageSize" value="original" checked>
                            原始尺寸
                        </label>
                        <label style="display: block; margin-bottom: 10px;">
                            <input type="radio" name="imageSize" value="large">
                            大尺寸 (最大宽度 800px)
                        </label>
                        <label style="display: block; margin-bottom: 10px;">
                            <input type="radio" name="imageSize" value="medium">
                            中等尺寸 (最大宽度 600px)
                        </label>
                        <label style="display: block; margin-bottom: 10px;">
                            <input type="radio" name="imageSize" value="small">
                            小尺寸 (最大宽度 400px)
                        </label>
                        <label style="display: block; margin-bottom: 10px;">
                            <input type="radio" name="imageSize" value="custom">
                            自定义尺寸
                        </label>
                        <div id="customSizeInputs" style="display: none; margin-left: 20px;">
                            <input type="number" id="customWidth" placeholder="宽度" style="width: 80px; margin-right: 10px;">
                            <input type="number" id="customHeight" placeholder="高度" style="width: 80px;">
                        </div>
                    </div>
                    <div class="modal-actions">
                        <button id="imageSizeCancel" class="btn btn-secondary">取消</button>
                        <button id="imageSizeOk" class="btn btn-primary">确定</button>
                    </div>
                </div>
            `;

            document.body.appendChild(dialog);

            const customRadio = dialog.querySelector('input[value="custom"]');
            const customInputs = dialog.getElementById('customSizeInputs');
            const customWidth = dialog.getElementById('customWidth');
            const customHeight = dialog.getElementById('customHeight');

            // 监听自定义选项
            customRadio.addEventListener('change', () => {
                customInputs.style.display = customRadio.checked ? 'block' : 'none';
                if (customRadio.checked) {
                    customWidth.focus();
                }
            });

            dialog.querySelectorAll('input[name="imageSize"]').forEach(radio => {
                radio.addEventListener('change', () => {
                    customInputs.style.display = radio.value === 'custom' ? 'block' : 'none';
                });
            });

            const handleOk = () => {
                const selectedSize = dialog.querySelector('input[name="imageSize"]:checked').value;
                let markup = '';

                switch (selectedSize) {
                    case 'large':
                        markup = `<img src="${url}" alt="${altText}" style="max-width: 800px; height: auto;">`;
                        break;
                    case 'medium':
                        markup = `<img src="${url}" alt="${altText}" style="max-width: 600px; height: auto;">`;
                        break;
                    case 'small':
                        markup = `<img src="${url}" alt="${altText}" style="max-width: 400px; height: auto;">`;
                        break;
                    case 'custom':
                        const width = customWidth.value;
                        const height = customHeight.value;
                        if (width || height) {
                            const style = [];
                            if (width) style.push(`width: ${width}px`);
                            if (height) style.push(`height: ${height}px`);
                            markup = `<img src="${url}" alt="${altText}" style="${style.join('; ')};">`;
                        } else {
                            markup = `![${altText}](${url})`;
                        }
                        break;
                    default:
                        markup = `![${altText}](${url})`;
                }

                document.body.removeChild(dialog);
                resolve({ markup });
            };

            const handleCancel = () => {
                document.body.removeChild(dialog);
                resolve({ cancelled: true });
            };

            dialog.getElementById('imageSizeOk').addEventListener('click', handleOk);
            dialog.getElementById('imageSizeCancel').addEventListener('click', handleCancel);
        });
    }

    replaceRecentlyInsertedImage(url, markup) {
        if (!window.editorManager?.editorInstance) return;

        const content = window.editorManager.editorInstance.getMarkdown();
        const escapedUrl = url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const imagePattern = new RegExp(`!\\[Image\\]\\(${escapedUrl}\\)`, 'g');
        const newContent = content.replace(imagePattern, markup);

        if (newContent !== content) {
            window.editorManager.editorInstance.setMarkdown(newContent, false);
        }
    }

    optimizeImageForWeb(file, maxWidth = 1920, quality = 0.8) {
        return new Promise((resolve) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();

            img.onload = () => {
                const { width, height } = img;

                // 计算新尺寸
                let newWidth = width;
                let newHeight = height;

                if (width > maxWidth) {
                    newWidth = maxWidth;
                    newHeight = (height * maxWidth) / width;
                }

                canvas.width = newWidth;
                canvas.height = newHeight;

                // 绘制图片
                ctx.drawImage(img, 0, 0, newWidth, newHeight);

                // 转换为Blob
                canvas.toBlob((blob) => {
                    resolve(blob);
                }, file.type, quality);
            };

            img.onerror = () => {
                resolve(file); // 如果处理失败，返回原文件
            };

            img.src = URL.createObjectURL(file);
        });
    }

    isImageFile(file) {
        return file.type.startsWith('image/');
    }

    isVideoFile(file) {
        return file.type.startsWith('video/');
    }

    getSupportedImageFormats() {
        return ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'];
    }

    getSupportedVideoFormats() {
        return ['video/mp4', 'video/webm', 'video/ogg'];
    }

    validateMediaFile(file) {
        const supportedImages = this.getSupportedImageFormats();
        const supportedVideos = this.getSupportedVideoFormats();

        if (this.isImageFile(file)) {
            return supportedImages.includes(file.type);
        }

        if (this.isVideoFile(file)) {
            return supportedVideos.includes(file.type);
        }

        return false;
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

// 导出单例
window.imageUtils = new ImageUtils();
