(() => {
  const site = {
    version: "1.8.10",
    repo: "https://github.com/Pugmaster04/Format-Foundry",
    releasePage: "https://github.com/Pugmaster04/Format-Foundry/releases/latest",
    links: {
      windowsInstaller: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry_Setup.exe",
      windowsPortable: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry.exe",
      windowsUpdater: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry_Updater.exe",
      linuxDeb: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/format-foundry_latest_amd64.deb",
      linuxAppImage: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry_linux_latest_x86_64.AppImage",
      linuxTarball: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry_linux_x86_64.tar.gz",
    },
    lists: {
      windowsAlt: [
        {
          href: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry.exe",
          title: "Portable Windows app",
          description: "Single-file executable when you do not want the installer path.",
          action: "Download EXE",
        },
        {
          href: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry_Updater.exe",
          title: "Standalone updater",
          description: "Separate updater binary for manual update workflows.",
          action: "Download updater",
        },
      ],
      linuxAlt: [
        {
          href: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry_linux_latest_x86_64.AppImage",
          title: "Linux AppImage",
          description: "Portable self-contained build when you do not want a system package install.",
          action: "Download AppImage",
        },
        {
          href: "https://github.com/Pugmaster04/Format-Foundry/releases/latest/download/FormatFoundry_linux_x86_64.tar.gz",
          title: "Linux tarball",
          description: "Raw packaged bundle for manual extraction or archive workflows.",
          action: "Download tarball",
        },
      ],
    },
  };

  document.querySelectorAll("[data-version]").forEach((node) => {
    node.textContent = site.version;
  });

  document.querySelectorAll("[data-link]").forEach((node) => {
    const key = node.getAttribute("data-link");
    if (key === "repo" || key === "releasePage") {
      node.href = site[key];
      return;
    }
    if (site.links[key]) {
      node.href = site.links[key];
    }
  });

  document.querySelectorAll("[data-render-list]").forEach((node) => {
    const listKey = node.getAttribute("data-render-list");
    const items = site.lists[listKey] || [];
    node.innerHTML = items
      .map(
        (item) => `
      <a class="asset-link" href="${item.href}">
        <span>
          <strong>${item.title}</strong>
          <span>${item.description}</span>
        </span>
        <em>${item.action}</em>
      </a>
    `,
      )
      .join("");
  });

  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.18, rootMargin: "0px 0px -8% 0px" },
    );

    document.querySelectorAll(".reveal").forEach((node) => observer.observe(node));
  } else {
    document.querySelectorAll(".reveal").forEach((node) => node.classList.add("is-visible"));
  }
})();
