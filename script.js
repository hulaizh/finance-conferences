
const toggleMobileMenu = () => {
  const toggle = document.querySelector('.mobile-menu-toggle');
  const navLinks = document.querySelector('.nav-links');
  
  toggle?.classList.toggle('active');
  navLinks?.classList.toggle('active');
};

document.addEventListener('click', (event) => {
  const toggle = document.querySelector('.mobile-menu-toggle');
  const navLinks = document.querySelector('.nav-links');
  
  if (toggle && navLinks && !toggle.contains(event.target) && !navLinks.contains(event.target)) {
    toggle.classList.remove('active');
    navLinks.classList.remove('active');
  }
}, { passive: true });\n\n
