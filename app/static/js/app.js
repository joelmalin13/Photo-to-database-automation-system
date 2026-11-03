/**
 * SnapBase Client-side Interactive Utilities
 * Handles Lucide SVG icon rendering, HTMX life-cycle hooks, toasts, and viewer controls.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Initialize Lucide icons on initial page load
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Global Review Keyboard Shortcuts
  document.addEventListener("keydown", (e) => {
    // Only trigger if review controls exist on page
    const approveBtn = document.getElementById("btn-approve-document");
    const rejectBtn = document.getElementById("btn-reject-document");

    if (e.ctrlKey && e.key === "Enter" && approveBtn) {
      e.preventDefault();
      approveBtn.click();
    } else if (e.key === "Escape" && rejectBtn) {
      e.preventDefault();
      rejectBtn.click();
    }
  });
});

// Re-render icons on HTMX DOM swaps
document.body.addEventListener("htmx:afterSwap", () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }
});

/**
 * Display a modern toast notification.
 * @param {string} message - Notification text
 * @param {'success'|'error'|'info'} type - Toast severity
 */
window.showToast = function (message, type = "success") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  const bgClasses =
    type === "error"
      ? "bg-rose-900 text-rose-100 border-rose-700"
      : type === "info"
      ? "bg-gray-900 text-gray-100 border-gray-700"
      : "bg-emerald-900 text-emerald-100 border-emerald-700";

  toast.className = `toast-message px-4 py-3 rounded-lg shadow-lg border text-sm font-medium flex items-center justify-between gap-3 ${bgClasses}`;
  toast.innerHTML = `
    <span>${message}</span>
    <button onclick="this.parentElement.remove()" class="opacity-75 hover:opacity-100 text-lg leading-none">&times;</button>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
};

/**
 * Image Viewer Pan & Zoom State Factory (Alpine.js compatible)
 */
window.imageViewer = function () {
  return {
    scale: 1,
    rotation: 0,
    isPanning: false,
    startX: 0,
    startY: 0,
    translateX: 0,
    translateY: 0,

    zoomIn() {
      this.scale = Math.min(this.scale + 0.25, 3.5);
    },
    zoomOut() {
      this.scale = Math.max(this.scale - 0.25, 0.5);
    },
    rotate() {
      this.rotation = (this.rotation + 90) % 360;
    },
    reset() {
      this.scale = 1;
      this.rotation = 0;
      this.translateX = 0;
      this.translateY = 0;
    },
    startPan(e) {
      this.isPanning = true;
      this.startX = e.clientX - this.translateX;
      this.startY = e.clientY - this.translateY;
    },
    pan(e) {
      if (!this.isPanning) return;
      this.translateX = e.clientX - this.startX;
      this.translateY = e.clientY - this.startY;
    },
    endPan() {
      this.isPanning = false;
    },
    get transformStyle() {
      return `transform: translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale}) rotate(${this.rotation}deg);`;
    },
  };
};
