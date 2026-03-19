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

        fmText.split('\n').forEach((line) => {
            const separator = line.indexOf(':');
            if (separator === -1) return;
            const key = line.slice(0, separator).trim();
            const value = line.slice(separator + 1).trim();
            metadata[key] = value;
        });

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
        const slugFallback = (String(currentFilePath || '').split('/').pop() || 'post').replace(/\.md$/i, '');

        if (this.metaTitleInput) {
            this.metaTitleInput.value = this.unwrapFrontMatterValue(metadata.title) || hints.title || '';
        }
        if (this.metaSlugInput) {
            this.metaSlugInput.value = this.unwrapFrontMatterValue(metadata.slug) || slugFallback;
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
            this.metaCoverInput.value = this.unwrapFrontMatterValue(metadata.cover) || hints.cover || '';
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
        const slug = this.metaSlugInput?.value.trim() || '';
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
            if (coverLower === 'none' || coverLower === 'false') {
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

    fillMetaPanel() {
        const editorInstance = window.editorManager?.editorInstance;
        if (!editorInstance) return;

        const content = editorInstance.getMarkdown();
        const parsed = this.splitFrontMatter(content);
        this.fillMetaPanelFromState({
            bodyContent: parsed.body,
            metadata: parsed.metadata,
            currentFilePath: window.editorManager?.currentFilePath || '',
        });
    }

    ensureFrontMatterBlock() {
        this.fillMetaPanel();
    }
}

window.frontMatterUtils = new FrontMatterUtils();
