const toggleMobileMenu = () => {
  console.log('toggleMobileMenu called');
  const toggle = document.querySelector('.mobile-menu-toggle');
  const navLinks = document.querySelector('.nav-links');

  console.log('Toggle element:', toggle);
  console.log('NavLinks element:', navLinks);

  toggle?.classList.toggle('active');
  navLinks?.classList.toggle('active');

  console.log('Toggle has active:', toggle?.classList.contains('active'));
  console.log('NavLinks has active:', navLinks?.classList.contains('active'));
};

document.addEventListener('click', (event) => {
  const toggle = document.querySelector('.mobile-menu-toggle');
  const navLinks = document.querySelector('.nav-links');

  if (toggle && navLinks && !toggle.contains(event.target) && !navLinks.contains(event.target)) {
    toggle.classList.remove('active');
    navLinks.classList.remove('active');
  }
}, { passive: true });