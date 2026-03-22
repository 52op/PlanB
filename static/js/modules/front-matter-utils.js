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
        this.metaUpdatedInput = document.getElementById('metaUpdated');
        this.metaTemplateSelect = document.getElementById('metaTemplate');
        this.metaPublicCheck = document.getElementById('metaPublic');
        this.metaDraftCheck = document.getElementById('metaDraft');
    }

    splitFrontMatter(content) {
        const text = String(content || '');
        if (!text.startsWith('---\n')) {
            return { metadata: {}, body: text, frontMatterText: '', hasFrontMatter: false };
        }

        const endIndex = text.indexOf('\n---\n', 4);
        if (endIndex === -1) {
            return { metadata: {}, body: text, frontMatterText: '', hasFrontMatter: false };
        }

        const fmText = text.slice(4, endIndex);
        const body = text.slice(endIndex + 5);
        const metadata = {};
        const lines = fmText.split('\n');
        let currentListKey = '';
        let currentListValues = [];

        const flushListValue = () => {
            if (!currentListKey) return;
            metadata[currentListKey] = `[${currentListValues.join(', ')}]`;
            currentListKey = '';
            currentListValues = [];
        };

        lines.forEach((line) => {
            const trimmedLine = line.trim();

            if (currentListKey) {
                if (trimmedLine.startsWith('- ')) {
                    currentListValues.push(trimmedLine.slice(2).trim());
                    return;
                }

                if (!trimmedLine) {
                    return;
                }

                flushListValue();
            }

            const separator = line.indexOf(':');
            if (separator === -1) return;

            const key = line.slice(0, separator).trim();
            const value = line.slice(separator + 1).trim();

            if (!value) {
                currentListKey = key;
                currentListValues = [];
                metadata[key] = '';
                return;
            }

            metadata[key] = value;
        });

        flushListValue();

        return {
            metadata,
            body,
            frontMatterText: `---\n${fmText}\n---`,
            hasFrontMatter: true,
        };
    }

    unwrapFrontMatterValue(value) {
        if (value === undefined || value === null) return '';
        const text = String(value).trim();
        if (!text) return '';

        if ((text.startsWith('"') && text.endsWith('"')) || (text.startsWith("'") && text.endsWith("'"))) {
            return text.slice(1, -1).replace(/''/g, "'");
        }

        return text;
    }

    parseFrontMatterBoolean(value) {
        return ['true', 'True', '1'].includes(String(value || '').trim());
    }

    normalizeCoverFieldValue(value) {
        const text = this.unwrapFrontMatterValue(value);
        return ['__NONE__', '__none__'].includes(text) ? 'none' : text;
    }

    slugifyValue(value) {
        const text = String(value || '').trim().toLowerCase();
        if (!text) return 'post';

        const normalized = text.normalize('NFKD');
        const slugSource = normalized.replace(/[\u0300-\u036f]/g, '');
        const slug = slugSource
            .replace(/[^\w\u4e00-\u9fff-]+/gu, '-')
            .replace(/-{2,}/g, '-')
            .replace(/^[-_]+|[-_]+$/g, '');

        return slug || 'post';
    }

    escapeYamlValue(value) {
        if (!value) return value;
        const text = String(value);
        const needsQuoting =
            /[:\n\r"'#\[\]{}|>@`!%&*]/.test(text) ||
            text.startsWith(' ') ||
            text.endsWith(' ') ||
            text.startsWith('-') ||
            /^\d+$/.test(text) ||
            /^(true|false|yes|no|null)$/i.test(text);

        if (!needsQuoting) {
            return text;
        }

        return `'${text.replace(/'/g, "''")}'`;
    }

    extractFrontMatterHints(content) {
        const text = String(content || '');
        const titleMatch = text.match(/^#\s+(.+)$/m);
        const markdownImage = text.match(/!\[[^\]]*\]\(([^)\s]+)[^)]*\)/);
        const htmlImage = text.match(/<img[^>]+src=["']([^"']+)["']/i);
        const stripped = text
            .replace(/^---[\s\S]*?---\s*/m, '')
            .replace(/[#>*`_\-]+/g, ' ')
            .replace(/!\[[^\]]*\]\((.*?)\)/g, ' ')
            .replace(/<[^>]+>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();

        return {
            title: titleMatch ? titleMatch[1].trim() : '',
            cover: markdownImage ? markdownImage[1].trim() : (htmlImage ? htmlImage[1].trim() : ''),
            summary: stripped ? `${stripped.slice(0, 140)}${stripped.length > 140 ? '...' : ''}` : '',
        };
    }

    fillMetaPanelFromState({ bodyContent = '', metadata = {}, currentFilePath = '' } = {}) {
        if (!this.metaPanel) return;

        const hints = this.extractFrontMatterHints(bodyContent);
        const fileBaseName = (String(currentFilePath || '').split('/').pop() || 'post').replace(/\.md$/i, '');
        const existingSlug = this.unwrapFrontMatterValue(metadata.slug);
        const titleValue = this.unwrapFrontMatterValue(metadata.title) || hints.title || '';
        const slugFallback = existingSlug || titleValue || fileBaseName;

        if (this.metaTitleInput) {
            this.metaTitleInput.value = titleValue;
        }
        if (this.metaSlugInput) {
            this.metaSlugInput.value = slugFallback;
        }
        if (this.metaDateInput) {
            this.metaDateInput.value = this.unwrapFrontMatterValue(metadata.date) || '';
        }
        if (this.metaUpdatedInput) {
            this.metaUpdatedInput.value = this.unwrapFrontMatterValue(metadata.updated) || new Date().toISOString().slice(0, 10);
        }
        if (this.metaTemplateSelect) {
            this.metaTemplateSelect.value = this.unwrapFrontMatterValue(metadata.template) || 'post';
        }
        if (this.metaTagsInput) {
            this.metaTagsInput.value = this
                .unwrapFrontMatterValue(metadata.tags)
                .replace(/^\[(.*)\]$/, '$1')
                .replace(/['"]+/g, '')
                .replace(/\s*,\s*/g, ', ');
        }
        if (this.metaSummaryInput) {
            this.metaSummaryInput.value = this.unwrapFrontMatterValue(metadata.summary) || hints.summary || '';
        }
        if (this.metaCoverInput) {
            this.metaCoverInput.value = this.normalizeCoverFieldValue(metadata.cover) || hints.cover || '';
        }
        if (this.metaPublicCheck) {
            this.metaPublicCheck.checked = this.parseFrontMatterBoolean(metadata.public);
        }
        if (this.metaDraftCheck) {
            this.metaDraftCheck.checked = this.parseFrontMatterBoolean(metadata.draft);
        }
    }

    buildFrontMatterFromPanel(bodyContent) {
        const title = this.metaTitleInput?.value.trim() || '';
        const rawSlug = this.metaSlugInput?.value.trim() || '';
        const slug = rawSlug ? this.slugifyValue(rawSlug) : '';
        const date = this.metaDateInput?.value.trim() || '';
        const updated = this.metaUpdatedInput?.value.trim() || new Date().toISOString().slice(0, 10);
        const template = this.metaTemplateSelect?.value || 'post';
        const tags = (this.metaTagsInput?.value || '')
            .split(',')
            .map((item) => item.trim())
            .filter(Boolean);
        const summary = this.metaSummaryInput?.value.trim() || '';
        const cover = this.metaCoverInput?.value.trim() || '';
        const isPublic = !!this.metaPublicCheck?.checked;
        const isDraft = !!this.metaDraftCheck?.checked;

        const lines = ['---'];
        if (title) lines.push(`title: ${this.escapeYamlValue(title)}`);
        if (date) lines.push(`date: ${date}`);
        lines.push(`updated: ${updated}`);
        if (summary) lines.push(`summary: ${this.escapeYamlValue(summary)}`);
        lines.push(`tags: [${tags.map((tag) => this.escapeYamlValue(tag)).join(', ')}]`);

        if (cover) {
            const coverLower = cover.toLowerCase();
            if (coverLower === 'none' || coverLower === 'false' || coverLower === '__none__') {
                lines.push(`cover: ${coverLower}`);
            } else {
                lines.push(`cover: ${this.escapeYamlValue(cover)}`);
            }
        } else {
            lines.push('cover: ');
        }

        lines.push(`template: ${template}`);
        lines.push(`public: ${isPublic ? 'true' : 'false'}`);
        lines.push(`draft: ${isDraft ? 'true' : 'false'}`);
        if (slug) lines.push(`slug: ${this.escapeYamlValue(slug)}`);
        lines.push('---', '', String(bodyContent || '').replace(/^\n+/, ''));

        return lines.join('\n');
    }

    getPanelState() {
        return {
            title: this.metaTitleInput?.value.trim() || '',
            slug: this.metaSlugInput?.value.trim() || '',
            date: this.metaDateInput?.value.trim() || '',
            updated: this.metaUpdatedInput?.value.trim() || '',
            template: this.metaTemplateSelect?.value || 'post',
            tags: this.metaTagsInput?.value.trim() || '',
            summary: this.metaSummaryInput?.value.trim() || '',
            cover: this.metaCoverInput?.value.trim() || '',
            public: !!this.metaPublicCheck?.checked,
            draft: !!this.metaDraftCheck?.checked,
        };
    }

}

window.frontMatterUtils = new FrontMatterUtils();
