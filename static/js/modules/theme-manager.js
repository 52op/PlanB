/**
 * Theme Manager Module
 * Handles theme switching, localStorage persistence, and dark mode toggle
 */
class ThemeManager {
  constructor() {
    this.storageAvailable = this.checkStorageAvailability();
    this.currentTheme = null;
    this.currentMode = null;
  }

  /**
   * Check if localStorage is available
   */
  checkStorageAvailability() {
    try {
      localStorage.setItem('theme_test', '1');
      localStorage.removeItem('theme_test');
      return true;
    } catch (e) {
      console.warn('[ThemeManager] localStorage not available, using session-only theme');
      return false;
    }
  }

  /**
   * Load theme color from localStorage or default
   */
  loadTheme() {
    if (this.storageAvailable) {
      const stored = localStorage.getItem('theme_color');
      if (stored) return stored;
    }
    return document.documentElement.dataset.defaultTheme || 'blue';
  }

  /**
   * Load theme mode from localStorage, system preference, or default
   */
  loadMode() {
    if (this.storageAvailable) {
      const stored = localStorage.getItem('theme_mode');
      if (stored) return stored;
    }

    const defaultMode = document.documentElement.dataset.defaultMode || 'light';
    if (defaultMode === 'auto') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return defaultMode;
  }

  /**
   * Apply theme color and mode to the document
   */
  applyTheme(color, mode) {
    document.documentElement.setAttribute('data-theme-color', color);
    document.documentElement.setAttribute('data-theme', mode);

    if (this.storageAvailable) {
      localStorage.setItem('theme_color', color);
      localStorage.setItem('theme_mode', mode);
    }

    this.currentTheme = color;
    this.currentMode = mode;

    // Emit event for other components
    if (window.planningApp) {
      window.planningApp.emit('theme-changed', { color, mode });
    }

    this.updateModeIcon();
    this.updateActiveButton();

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  /**
   * Toggle between light and dark mode
   */
  toggleMode() {
    const newMode = this.currentMode === 'light' ? 'dark' : 'light';
    this.applyTheme(this.currentTheme, newMode);
  }

  /**
   * Set theme color
   */
  setTheme(color) {
    this.applyTheme(color, this.currentMode);
  }

  updateModeIcon() {
    const buttons = [
      document.getElementById('modeToggleBtn'),
      document.getElementById('modeToggleBtnQuick')
    ].filter(Boolean);
    if (!buttons.length) return;

    buttons.forEach((btn) => {
      const icon = btn.querySelector('svg[data-lucide], i[data-lucide]');
      if (icon) {
        icon.setAttribute('data-lucide', this.currentMode === 'dark' ? 'sun' : 'moon');
      }
    });

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  /**
   * Update active state of theme color buttons
   */
  updateActiveButton() {
    document.querySelectorAll('.theme-color-btn').forEach(btn => {
      if (btn.dataset.theme === this.currentTheme) {
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
      } else {
        btn.classList.remove('active');
        btn.setAttribute('aria-pressed', 'false');
      }
    });
  }

  /**
   * Initialize theme manager
   */
  initialize() {
    // Load and apply saved theme
    this.currentTheme = this.loadTheme();
    this.currentMode = this.loadMode();

    // Ensure initial icons are rendered before stateful updates
    if (window.lucide) {
      window.lucide.createIcons();
    }

    this.applyTheme(this.currentTheme, this.currentMode);

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
      const defaultMode = document.documentElement.dataset.defaultMode;
      if (defaultMode === 'auto' && !this.storageAvailable) {
        this.applyTheme(this.currentTheme, e.matches ? 'dark' : 'light');
      }
    });

    this.bindEvents();
  }

  /**
   * Bind event listeners
   */
  bindEvents() {
    const dropdown = document.getElementById('themeDropdown');
    const themeSelector = document.querySelector('.theme-selector');
    const themeMenu = document.querySelector('.theme-menu');
    const themeButtons = document.querySelectorAll('.theme-color-btn');
    const modeButton = document.getElementById('modeToggleBtn');
    const toggleButtons = [
      document.getElementById('themeToggleBtn'),
      document.getElementById('themeToggleBtnDesktop'),
      document.getElementById('themeToggleBtnMobile')
    ].filter(Boolean);

    const toggleContainers = [themeSelector, themeMenu].filter(Boolean);
    const setDropdownOpen = (isOpen) => {
      if (!dropdown) return;
      dropdown.classList.toggle('show', isOpen);
      dropdown.style.pointerEvents = isOpen ? 'auto' : '';
      toggleContainers.forEach((container) => {
        container.classList.toggle('show', isOpen);
      });
    };

    themeButtons.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const theme = btn.dataset.theme;
        if (theme) {
          this.setTheme(theme);
        }
      });
    });

    if (modeButton) {
      modeButton.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.toggleMode();
      });
    }

    toggleButtons.forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (dropdown) {
          setDropdownOpen(!dropdown.classList.contains('show'));
        }
      });
    });

    document.addEventListener('click', (e) => {
      const clickedToggle = toggleButtons.some((btn) => btn.contains(e.target));
      const clickedContainer = toggleContainers.some((container) => container.contains(e.target));
      if (dropdown && !dropdown.contains(e.target) && !clickedToggle && !clickedContainer) {
        setDropdownOpen(false);
      }
    });
  }
}

// Create global instance
window.themeManager = new ThemeManager();
