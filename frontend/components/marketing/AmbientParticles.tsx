/**
 * components/marketing/AmbientParticles.tsx
 * =============================================
 * Lightweight CSS-only particle trails (Full_Style_Description.txt:
 * "glowing neon green particle/light trails flowing across the bottom").
 * Deliberately cheap (no canvas) since the three.js orb already carries
 * the heavier animation budget for this page.
 */
const PARTICLES = Array.from({ length: 24 }, (_, i) => ({
  left: `${(i * 41.7) % 100}%`,
  bottom: `${(i * 17.3) % 60}%`,
  delay: `${(i % 8) * 0.9}s`,
  duration: `${7 + (i % 5)}s`,
  size: i % 3 === 0 ? 3 : 2,
}));

export function AmbientParticles() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
      {PARTICLES.map((p, i) => (
        <span
          key={i}
          className="absolute rounded-full bg-primary animate-float-particle"
          style={{
            left: p.left,
            bottom: p.bottom,
            width: p.size,
            height: p.size,
            animationDelay: p.delay,
            animationDuration: p.duration,
            boxShadow: "0 0 6px 1px hsl(156 100% 50% / 0.8)",
          }}
        />
      ))}
    </div>
  );
}
