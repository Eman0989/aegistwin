export default function HeroCoreMark() {
  return (
    <div className="sentinel-mark">
      <div className="sentinel-aura sentinel-aura--silver" />
      <div className="sentinel-aura sentinel-aura--gold" />

      <svg
        className="sentinel-svg"
        viewBox="0 0 700 700"
        aria-hidden="true"
      >
        <defs>
          <linearGradient
            id="sentinelSilver"
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="30%" stopColor="#dce3e9" />
            <stop offset="68%" stopColor="#7f8b97" />
            <stop offset="100%" stopColor="#e9eef2" />
          </linearGradient>

          <linearGradient
            id="sentinelGold"
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop offset="0%" stopColor="#fff2aa" />
            <stop offset="38%" stopColor="#e2b347" />
            <stop offset="72%" stopColor="#9c661b" />
            <stop offset="100%" stopColor="#f5d579" />
          </linearGradient>

          <linearGradient
            id="sentinelCore"
            x1="0"
            y1="0"
            x2="1"
            y2="1"
          >
            <stop offset="0%" stopColor="#f9fbff" />
            <stop offset="48%" stopColor="#f1d47d" />
            <stop offset="100%" stopColor="#b77a20" />
          </linearGradient>

          <radialGradient
            id="sentinelGlow"
            cx="50%"
            cy="50%"
            r="50%"
          >
            <stop offset="0%" stopColor="#fffdf2" />
            <stop offset="20%" stopColor="#ffe99e" />
            <stop offset="47%" stopColor="#e4b343" />
            <stop offset="100%" stopColor="#e4b34300" />
          </radialGradient>

          <filter
            id="sentinelCoreGlow"
            x="-100%"
            y="-100%"
            width="300%"
            height="300%"
          >
            <feGaussianBlur
              stdDeviation="18"
              result="blur"
            />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Outer precision frame */}

        <path
          className="sentinel-frame"
          d="
            M350 104
            L530 208
            L530 492
            L350 596
            L170 492
            L170 208
            Z
          "
        />

        <path
          className="sentinel-frame sentinel-frame--inner"
          d="
            M350 143
            L496 227
            L496 473
            L350 557
            L204 473
            L204 227
            Z
          "
        />

        {/* Left silver protective plate */}

        <path
          className="sentinel-panel sentinel-panel--silver"
          fill="url(#sentinelSilver)"
          d="
            M321 178
            L237 227
            L237 473
            L321 522
            L290 442
            L276 350
            L290 258
            Z
          "
        />

        {/* Right gold protective plate */}

        <path
          className="sentinel-panel sentinel-panel--gold"
          fill="url(#sentinelGold)"
          d="
            M379 178
            L463 227
            L463 473
            L379 522
            L410 442
            L424 350
            L410 258
            Z
          "
        />

        {/* Fine internal geometry */}

        <path
          className="sentinel-detail sentinel-detail--silver"
          d="
            M304 239
            L271 270
            L263 350
            L271 430
            L304 461
          "
        />

        <path
          className="sentinel-detail sentinel-detail--gold"
          d="
            M396 239
            L429 270
            L437 350
            L429 430
            L396 461
          "
        />

        {/* Protected central axis */}

        <line
          className="sentinel-axis"
          x1="350"
          y1="190"
          x2="350"
          y2="510"
        />

        {/* Energy halo */}

        <circle
          className="sentinel-halo"
          cx="350"
          cy="350"
          r="102"
        />

        <circle
          cx="350"
          cy="350"
          r="67"
          fill="url(#sentinelGlow)"
          filter="url(#sentinelCoreGlow)"
        />

        {/* Central diamond */}

        <path
          className="sentinel-diamond"
          fill="url(#sentinelCore)"
          d="
            M350 298
            L402 350
            L350 402
            L298 350
            Z
          "
        />

        <path
          className="sentinel-diamond-inner"
          d="
            M350 319
            L381 350
            L350 381
            L319 350
            Z
          "
        />

        <circle
          className="sentinel-center"
          cx="350"
          cy="350"
          r="8"
        />

        {/* Four restrained data anchors */}

        <circle className="sentinel-anchor sentinel-anchor--silver" cx="249" cy="282" r="4" />
        <circle className="sentinel-anchor sentinel-anchor--silver" cx="249" cy="418" r="4" />

        <circle className="sentinel-anchor sentinel-anchor--gold" cx="451" cy="282" r="4" />
        <circle className="sentinel-anchor sentinel-anchor--gold" cx="451" cy="418" r="4" />
      </svg>

      <span className="sentinel-particle sp-1" />
      <span className="sentinel-particle sp-2" />
      <span className="sentinel-particle sp-3" />
      <span className="sentinel-particle sp-4" />
    </div>
  );
}