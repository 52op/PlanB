class ShareUtils {
    buildShareText({ title, url, siteName }) {
        const safeTitle = (title || '内容分享').trim();
        const safeSiteName = (siteName || 'Planning').trim();
        return `【${safeSiteName}】与您分享：${safeTitle}\n${url}`;
    }

    async copyText(text) {
        const value = String(text || '');
        if (!value) {
            return false;
        }

        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(value);
            return true;
        }

        const textarea = document.createElement('textarea');
        textarea.value = value;
        textarea.setAttribute('readonly', 'readonly');
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();

        let success = false;
        try {
            success = document.execCommand('copy');
        } finally {
            textarea.remove();
        }
        return success;
    }

    async shareWithSystem({ title, text, url }) {
        if (!navigator.share) {
            return false;
        }

        await navigator.share({
            title: title || '',
            text: text || '',
            url: url || '',
        });
        return true;
    }

    openPlatformShare(platform, { title, text, url }) {
        const safeTitle = encodeURIComponent(title || '');
        const safeText = encodeURIComponent(text || '');
        const safeUrl = encodeURIComponent(url || '');

        const platformUrls = {
            qq: `https://connect.qq.com/widget/shareqq/index.html?url=${safeUrl}&title=${safeTitle}&desc=${safeText}`,
            qzone: `https://sns.qzone.qq.com/cgi-bin/qzshare/cgi_qzshare_onekey?url=${safeUrl}&title=${safeTitle}&summary=${safeText}`,
            weibo: `https://service.weibo.com/share/share.php?url=${safeUrl}&title=${safeText}`,
        };

        const shareUrl = platformUrls[platform];
        if (!shareUrl) {
            return false;
        }

        window.open(shareUrl, '_blank', 'noopener,noreferrer,width=920,height=720');
        return true;
    }

    renderQRCode(container, text) {
        if (!container) {
            return false;
        }

        container.innerHTML = '';
        if (!text || !window.QRCode) {
            return false;
        }

        const options = {
            text,
            width: 176,
            height: 176,
        };
        if (window.QRCode.CorrectLevel) {
            options.correctLevel = window.QRCode.CorrectLevel.M;
        }

        new window.QRCode(container, options);
        return true;
    }
}

window.shareUtils = new ShareUtils();
