document.querySelectorAll(".card").forEach(card => {
  card.addEventListener("mousemove", e => {
    const x = (window.innerWidth / 2 - e.pageX) / 25;
    const y = (window.innerHeight / 2 - e.pageY) / 25;
    card.style.transform = `rotateY(${x}deg) rotateX(${y}deg) scale(1.05)`;
  });

  card.addEventListener("mouseleave", () => {
    card.style.transform = "rotateY(0) rotateX(0) scale(1)";
  });
});
