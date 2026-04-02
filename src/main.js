/**
 * Copy-to-clipboard for code blocks
 */
export function initCopyButtons() {
  document.querySelectorAll('[data-copy-target]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const targetId = btn.getAttribute('data-copy-target')
      const target = document.getElementById(targetId)
      if (!target) return

      const text = target.textContent ?? ''
      try {
        await navigator.clipboard.writeText(text)
        btn.setAttribute('data-copied', 'true')
        btn.querySelector('[data-copy-label]').textContent = 'Copied!'
        setTimeout(() => {
          btn.removeAttribute('data-copied')
          btn.querySelector('[data-copy-label]').textContent = 'Copy'
        }, 2000)
      } catch {
        // Fallback for older browsers
        const ta = document.createElement('textarea')
        ta.value = text
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
    })
  })
}

/**
 * Mobile nav toggle
 */
export function initMobileNav() {
  const toggle = document.getElementById('mobile-nav-toggle')
  const menu = document.getElementById('mobile-nav-menu')
  if (!toggle || !menu) return

  toggle.addEventListener('click', () => {
    const isOpen = menu.getAttribute('data-open') === 'true'
    menu.setAttribute('data-open', String(!isOpen))
    menu.style.display = isOpen ? 'none' : 'flex'
    toggle.setAttribute('aria-expanded', String(!isOpen))
  })
}

/**
 * Smooth scroll for anchor links
 */
export function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener('click', (e) => {
      const href = anchor.getAttribute('href')
      if (!href || href === '#') return
      const target = document.querySelector(href)
      if (!target) return
      e.preventDefault()
      target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  })
}
