/**
 * Front Matter工具模块 - 处理YAML前置元数据的解析和操作
 */
class FrontMatterUtils {
    constructor() {
        this.initializeElements();
    }

    initializeElements() {
        this.metaPanel = document.getElementById('metaPanel');
        this.metaTitleInput = document.getElementById('metaTitle');
        this.metaSummaryInput = document.getElementById('metaSummary');
        this.metaTagsInput = document.getElementById('metaTags');
        this.metaCoverInput = document.getElementById('metaCover');
        this.metaSlugInput = document.getElementById('metaSlug');
        this.metaDateInput = document.getElementById('metaDate');
        this.metaTemplateSelect = document.getElementById('metaTemplate');
        this.metaPublicCheck = document.getElementById('metaPublic');
        this.metaDraftCheck = document.getElementById('metaDraft');
    }

    splitFrontMatter(content) {
        if (!content.startsWith('---')) {
            return { metadata: {}, body: content };
        }

        const lines = content.split('\n');
        let endIndex = -1;

        for (let i = 1; i < lines.length; i++) {
            if (lines[i].trim() === '---') {
                endIndex = i;
                break;
            }
        }

        if (endIndex === -1) {
            return { metadata: {}, body: content };
        }

        const frontMatterText = lines.slice(1, endIndex).join('\n');
        const body = lines.slice(endIndex + 1).join('\n');

        try {
            // 简单的YAML解析（仅支持基本键值对）
            const metadata = this.parseSimpleYAML(frontMatterText);
            return { metadata, body };
        } catch (error) {
            console.warn('Failed to parse front matter:', error);
            return { metadata: {}, body: content };
        }
    }

    parseSimpleYAML(yamlText) {
        const metadata = {};
        const lines = yamlText.split('\n');

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) continue;

            const colonIndex = trimmed.indexOf(':');
            if (colonIndex === -1) continue;

            const key = trimmed.substring(0, colonIndex).trim();
            let value = trimmed.substring(colonIndex + 1).trim();

            // 处理引号
            if ((value.startsWith('"') && value.endsWith('"')) ||
                (value.startsWith("'") && value.endsWith("'"))) {
                value = value.slice(1, -1);
            }

            // 处理布尔值
            if (value === 'true') value = true;
            else if (value === 'false') value = false;

            // 处理数组（简单的逗号分隔）
            if (key === 'tags' && value.includes(',')) {
                value = value.split(',').map(tag => tag.trim()).filter(tag => tag);
            }

            metadata[key] = value;
        }

        return metadata;
    }

    buildFrontMatterFromPanel(bodyContent) {
        if (!this.metaPanel) return bodyContent;

        const metadata = {};

        if (this.metaTitleInput?.value.trim()) {
            metadata.title = this.metaTitleInput.value.trim();
        }

        if (this.metaSummaryInput?.value.trim()) {
            metadata.summary = this.metaSummaryInput.value.trim();
        }

        if (this.metaTagsInput?.value.trim()) {
            const tags = this.metaTagsInput.value.split(',')
                .map(tag => tag.trim())
                .filter(tag => tag);
            if (tags.length > 0) {
                metadata.tags = tags;
            }
        }

        if (this.metaCoverInput?.value.trim()) {
            metadata.cover = this.metaCoverInput.value.trim();
        }

        if (this.metaSlugInput?.value.trim()) {
            metadata.slug = this.metaSlugInput.value.trim();
        }

        if (this.metaDateInput?.value.trim()) {
            metadata.date = this.metaDateInput.value.trim();
        }

        if (this.metaTemplateSelect?.value && this.metaTemplateSelect.value !== 'doc') {
            metadata.template = this.metaTemplateSelect.value;
        }

        if (this.metaPublicCheck?.checked) {
            metadata.public = true;
        }

        if (this.metaDraftCheck?.checked) {
            metadata.draft = true;
        }

        // 自动添加更新时间
        metadata.updated = new Date().toISOString().split('T')[0];

        return this.buildFrontMatterContent(metadata, bodyContent);
    }

    buildFrontMatterContent(metadata, bodyContent) {
        if (Object.keys(metadata).length === 0) {
            return bodyContent;
        }

        const yamlLines = ['---'];

        // 按特定顺序输出字段
        const fieldOrder = ['title', 'date', 'updated', 'summary', 'tags', 'cover', 'template', 'public', 'draft', 'slug'];

        for (const field of fieldOrder) {
            if (metadata.hasOwnProperty(field)) {
                const value = metadata[field];
                if (Array.isArray(value)) {
                    yamlLines.push(`${field}: [${value.map(v => `"${v}"`).join(', ')}]`);
                } else if (typeof value === 'string') {
                    yamlLines.push(`${field}: "${value}"`);
                } else {
                    yamlLines.push(`${field}: ${value}`);
                }
            }
        }

        // 添加其他未在顺序中的字段
        for (const [key, value] of Object.entries(metadata)) {
            if (!fieldOrder.includes(key)) {
                if (Array.isArray(value)) {
                    yamlLines.push(`${key}: [${value.map(v => `"${v}"`).join(', ')}]`);
                } else if (typeof value === 'string') {
                    yamlLines.push(`${key}: "${value}"`);
                } else {
                    yamlLines.push(`${key}: ${value}`);
                }
            }
        }

        yamlLines.push('---');
        yamlLines.push('');

        return yamlLines.join('\n') + bodyContent.replace(/^\n+/, '');
    }

    fillMetaPanel() {
        if (!this.metaPanel || !window.editorManager?.editorInstance) return;

        const content = window.editorManager.editorInstance.getMarkdown();
        const parsed = this.splitFrontMatter(content);
        const metadata = parsed.metadata;

        if (this.metaTitleInput) {
            this.metaTitleInput.value = metadata.title || '';
        }

        if (this.metaSummaryInput) {
            this.metaSummaryInput.value = metadata.summary || '';
        }

        if (this.metaTagsInput) {
            const tags = Array.isArray(metadata.tags) ? metadata.tags :
                         (metadata.tags ? [metadata.tags] : []);
            this.metaTagsInput.value = tags.join(', ');
        }

        if (this.metaCoverInput) {
            this.metaCoverInput.value = metadata.cover || '';
        }

        if (this.metaSlugInput) {
            this.metaSlugInput.value = metadata.slug || '';
        }

        if (this.metaDateInput) {
            this.metaDateInput.value = metadata.date || '';
        }

        if (this.metaTemplateSelect) {
            this.metaTemplateSelect.value = metadata.template || 'doc';
        }

        if (this.metaPublicCheck) {
            this.metaPublicCheck.checked = metadata.public === true;
        }

        if (this.metaDraftCheck) {
            this.metaDraftCheck.checked = metadata.draft === true;
        }
    }

    ensureFrontMatterBlock() {
        if (!window.editorManager?.editorInstance) return;

        const content = window.editorManager.editorInstance.getMarkdown();

        if (!content.startsWith('---')) {
            const newContent = this.buildFrontMatterContent({
                title: '',
                date: new Date().toISOString().split('T')[0],
                updated: new Date().toISOString().split('T')[0],
                template: 'doc',
                public: false,
                draft: false
            }, content);

            window.editorManager.editorInstance.setMarkdown(newContent, false);
        }
    }

    extractFirstHeading(content) {
        const match = content.match(/^#\s+(.+)$/m);
        return match ? match[1].trim() : '';
    }

    extractFirstImage(content) {
        // 匹配 Markdown 图片语法
        const markdownMatch = content.match(/!\[[^\]]*\]\(([^)\s]+)/);
        if (markdownMatch) {
            return markdownMatch[1].trim();
        }

        // 匹配 HTML img 标签
        const htmlMatch = content.match(/<img[^>]+src=["']([^"']+)["']/i);
        if (htmlMatch) {
            return htmlMatch[1].trim();
        }

        return '';
    }

    generateSlug(text) {
        return text
            .toLowerCase()
            .replace(/[^\w\u4e00-\u9fff\s-]/g, '') // 保留中文、英文、数字、空格、连字符
            .replace(/\s+/g, '-') // 空格替换为连字符
            .replace(/-+/g, '-') // 多个连字符合并为一个
            .replace(/^-|-$/g, ''); // 去除首尾连字符
    }

    autoFillMetadata() {
        if (!window.editorManager?.editorInstance) return;

        const content = window.editorManager.editorInstance.getMarkdown();
        const parsed = this.splitFrontMatter(content);
        const body = parsed.body;

        // 自动填充标题
        if (this.metaTitleInput && !this.metaTitleInput.value.trim()) {
            const heading = this.extractFirstHeading(body);
            if (heading) {
                this.metaTitleInput.value = heading;
            }
        }

        // 自动填充封面图片
        if (this.metaCoverInput && !this.metaCoverInput.value.trim()) {
            const image = this.extractFirstImage(body);
            if (image) {
                this.metaCoverInput.value = image;
            }
        }

        // 自动生成slug
        if (this.metaSlugInput && !this.metaSlugInput.value.trim() && this.metaTitleInput?.value.trim()) {
            this.metaSlugInput.value = this.generateSlug(this.metaTitleInput.value);
        }
    }
}

// 导出单例
window.frontMatterUtils = new FrontMatterUtils();