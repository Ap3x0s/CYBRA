import React from 'react'
import * as PhosphorIcons from '../icons'

/**
 * Custom SVG icons adapted to the CYBRA design system:
 * Dark theme (#141416 / #1f1f22), Amber accent #E5A93C, currentColor strokes/fills.
 */
export const CustomIcons = {
  // 1. iconoven:ci-pipeline-check (Runs / CI pipelines)
  'ci-pipeline-check': function CiPipelineCheck({ size = 16, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.6"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <rect width="4.5" height="5" x="2.75" y="12.5" rx="1.25" />
        <rect width="4.5" height="5" x="9.75" y="12.5" rx="1.25" />
        <rect width="4.5" height="5" x="16.75" y="12.5" rx="1.25" />
        <path d="M7.25 15h2.5m4.5 0h2.5m-12-4.75V8.5a3 3 0 0 1 3-3h8.5a3 3 0 0 1 3 3v1.75M17.5 8.5l1.75 1.75L21 8.5" />
      </svg>
    )
  },

  // 2. iconoven:exam-check (Checks / Test scenarios verification)
  'exam-check': function ExamCheck({ size = 16, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.6"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <rect width="16.5" height="18.5" x="3.75" y="2.75" rx="2.5" />
        <path d="M7.25 8L8.5 9.25l2.25-2.5M7.5 14.5l2.75 2.75m0-2.75L7.5 17.25M13.75 8h2.75m-2.75 7.75h2.75" />
      </svg>
    )
  },

  // 3. pixelarticons:ai-scan (AI scanning reticle)
  'ai-scan': function AiScan({ size = 16, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="currentColor"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path d="M9 11h2v2H9zm4 0h2v2h-2zM7 7h10v2H7zM5 9h2v6H5zm2 6h10v2H7zm10-6h2v6h-2zm-6-4h2v2h-2zM4 2h4v2H4zm0 18h4v2H4zM16 2h4v2h-4zm0 18h4v2h-4zM2 4h2v4H2zm0 12h2v4H2zM20 4h2v4h-2zm0 12h2v4h-2z" />
      </svg>
    )
  },

  // 4a. streamline-flex-color:ai-chip-robot (styled in CYBRA Amber duotone)
  'ai-chip-robot': function AiChipRobot({ size = 16, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 14 14"
        width={size}
        height={size}
        fill="none"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path
          fill="rgba(229, 169, 60, 0.16)"
          stroke="currentColor"
          strokeWidth="0.9"
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M2.758 10.315c.053.48.434.86.914.915c1.068.121 2.183.27 3.328.27s2.26-.149 3.328-.27c.48-.054.861-.435.914-.915C11.36 9.25 11.5 8.14 11.5 7s-.14-2.25-.258-3.315a1.04 1.04 0 0 0-.914-.915C9.26 2.649 8.145 2.5 7 2.5s-2.26.149-3.328.27c-.48.054-.861.435-.914.915C2.64 4.75 2.5 5.86 2.5 7s.14 2.25.258 3.315"
        />
        <path
          fill="var(--ink-700, #1f1f22)"
          stroke="currentColor"
          strokeWidth="0.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4.525 7.997V7.11a1.5 1.5 0 0 1 1.5-1.5h1.95a1.5 1.5 0 0 1 1.5 1.5v.888a1.5 1.5 0 0 1-1.5 1.5h-1.95a1.5 1.5 0 0 1-1.5-1.5Z"
        />
        <path
          stroke="currentColor"
          strokeWidth="0.9"
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M7 4.503v1.106m-.948 1.779v.33m1.895-.33v.33M.872 9.045H2.61m8.78 0h1.738m-3.993-6.42V.864m0 12.272v-1.745M.872 4.946H2.61m2.261-2.321V.864m6.519 4.082h1.738m-8.257 8.19v-1.745"
        />
      </svg>
    )
  },

  // 4b. streamline-flex-color:ai-chip-robot (pure clean outline version)
  'ai-chip-robot-outline': function AiChipRobotOutline({ size = 16, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 14 14"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeWidth="0.95"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path d="M2.758 10.315c.053.48.434.86.914.915c1.068.121 2.183.27 3.328.27s2.26-.149 3.328-.27c.48-.054.861-.435.914-.915C11.36 9.25 11.5 8.14 11.5 7s-.14-2.25-.258-3.315a1.04 1.04 0 0 0-.914-.915C9.26 2.649 8.145 2.5 7 2.5s-2.26.149-3.328.27c-.48.054-.861.435-.914.915C2.64 4.75 2.5 5.86 2.5 7s.14 2.25.258 3.315" />
        <path d="M4.525 7.997V7.11a1.5 1.5 0 0 1 1.5-1.5h1.95a1.5 1.5 0 0 1 1.5 1.5v.888a1.5 1.5 0 0 1-1.5 1.5h-1.95a1.5 1.5 0 0 1-1.5-1.5Z" />
        <path d="M7 4.503v1.106m-.948 1.779v.33m1.895-.33v.33M.872 9.045H2.61m8.78 0h1.738m-3.993-6.42V.864m0 12.272v-1.745M.872 4.946H2.61m2.261-2.321V.864m6.519 4.082h1.738m-8.257 8.19v-1.745" />
      </svg>
    )
  },

  // 5. iconmind:model-check-duotone-bold
  'model-check-duotone-bold': function ModelCheckDuotoneBold({ size = 20, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.2"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path
          fill="currentColor"
          d="M14.5 4H17a3 3 0 0 1 3 3v10a3 3 0 0 1 -3 3H7a3 3 0 0 1 -3 -3V8l4 -4h2.5"
          opacity=".2"
          stroke="none"
        />
        <path d="M14.5 4H17a3 3 0 0 1 3 3v10a3 3 0 0 1 -3 3H7a3 3 0 0 1 -3 -3V8l4 -4h2.5" />
        <path d="m8 12 2 2 6 -6" />
      </svg>
    )
  },

  // Custom Pixel-Perfect Handcrafted SVGs
  'custom-terminal': function CustomTerminal({ size = 16, className = '', style = {} }) {
    return (
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <polyline points="7,10 10,12 7,14" />
        <line x1="12" y1="14" x2="16" y2="14" />
      </svg>
    )
  },

  'custom-scan': function CustomScan({ size = 16, className = '', style = {} }) {
    return (
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path d="M7 3H5a2 2 0 0 0-2 2v2" />
        <path d="M17 3h2a2 2 0 0 1 2 2v2" />
        <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
        <path d="M3 17v2a2 2 0 0 0 2 2h2" />
        <circle cx="12" cy="12" r="3" />
        <line x1="12" y1="6" x2="12" y2="8" />
        <line x1="12" y1="16" x2="12" y2="18" />
        <line x1="6" y1="12" x2="8" y2="12" />
        <line x1="16" y1="12" x2="18" y2="12" />
      </svg>
    )
  },

  'custom-transformer': function CustomTransformer({ size = 16, className = '', style = {} }) {
    return (
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 12l10 5 10-5" />
        <path d="M2 17l10 5 10-5" />
      </svg>
    )
  },

  'custom-breached-shield': function CustomBreachedShield({ size = 16, className = '', style = {} }) {
    return (
      <svg
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <polyline points="13 7 10 12 14 12 11 17" />
      </svg>
    )
  },

  // 15. mdi:clipboard-text-history-outline — история проверок (Прогоны)
  'clipboard-text-history': function ClipboardTextHistory({ size = 16, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="currentColor"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path d="M21 11.11V5a2 2 0 0 0-2-2h-4.18C14.4 1.84 13.3 1 12 1s-2.4.84-2.82 2H5c-1.1 0-2 .9-2 2v14a2 2 0 0 0 2 2h6.11c1.26 1.24 2.98 2 4.89 2c3.87 0 7-3.13 7-7c0-1.91-.76-3.63-2-4.89M12 3c.55 0 1 .45 1 1s-.45 1-1 1s-1-.45-1-1s.45-1 1-1M5 19V5h2v2h10V5h2v4.68c-.91-.43-1.92-.68-3-.68H7v2h4.1c-.6.57-1.06 1.25-1.42 2H7v2h2.08c-.05.33-.08.66-.08 1c0 1.08.25 2.09.68 3zm11 2c-2.76 0-5-2.24-5-5s2.24-5 5-5s5 2.24 5 5s-2.24 5-5 5m.5-4.75l2.86 1.69l-.75 1.22L15 17v-5h1.5z" />
      </svg>
    )
  },

  // 16. material-symbols:work-history-outline — история прогонов
  'work-history': function WorkHistory({ size = 16, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="currentColor"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path d="M4 19V8zv-.375zm0 2q-.825 0-1.412-.587T2 19V8q0-.825.588-1.412T4 6h4V4q0-.825.588-1.412T10 2h4q.825 0 1.413.588T16 4v2h4q.825 0 1.413.588T22 8v4.275q-.45-.325-.95-.562T20 11.3V8H4v11h7.075q.075.525.225 1.025t.375.975zm6-15h4V4h-4zm4.463 15.538Q13 20.075 13 18t1.463-3.537T18 13t3.538 1.463T23 18t-1.463 3.538T18 23t-3.537-1.463M18.5 17.8V15h-1v3.2l2.15 2.15l.7-.7z" />
      </svg>
    )
  },

  // 17. iconmind:rollup-metric-outline-regular — метрики (столбики)
  'rollup-metric': function RollupMetric({ size = 16, className = '', style = {} }) {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        width={size}
        height={size}
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        className={className}
        style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
        aria-hidden="true"
      >
        <path d="M4 4v16" />
        <path d="M4 20h16" />
        <path d="M8 14v4" />
        <path d="M11 12v6" />
        <path d="M14 15v3" />
        <path d="M18 7v11" />
      </svg>
    )
  },
}

/**
 * Semantic map for AI Red Teaming platform domains.
 */
export const SEMANTIC_ICON_MAP = {
  // KPI на дашборде
  checks: CustomIcons['exam-check'],
  findings: PhosphorIcons.WarningOctagon,

  // Навигация — по рекомендациям Senior UX.
  // runs/models встречаются и в KPI, но там компоненты передают iconName
  // напрямую ('ai-scan'), поэтому конфликта нет.
  overview: PhosphorIcons.SquaresFour,
  runs: CustomIcons['ci-pipeline-check'],
  datasets: PhosphorIcons.Database,
  models: CustomIcons['ai-chip-robot-outline'],
  metrics: CustomIcons['rollup-metric'],
  settings: PhosphorIcons.SlidersHorizontal,

  // Quick actions
  'new-run': PhosphorIcons.Play,
  'compare-models': PhosphorIcons.ArrowsLeftRight,
  'edit-datasets': PhosphorIcons.Database,
  'run-history': PhosphorIcons.ClockCounterClockwise,
}

/**
 * Standard Unified Icon Component for CYBRA.
 */
export default function AppIcon({
  name,
  icon: DirectIcon,
  size = 16,
  weight = 'regular',
  chip = false,
  chipSize = 26,
  chipRadius = 7,
  className = '',
  style = {},
  ...rest
}) {
  let IconComponent = DirectIcon

  if (!IconComponent && typeof name === 'string') {
    // 1. Check custom SVG icons
    if (CustomIcons[name]) {
      IconComponent = CustomIcons[name]
    }
    // 2. Check semantic map
    else if (SEMANTIC_ICON_MAP[name]) {
      IconComponent = SEMANTIC_ICON_MAP[name]
    }
    // 3. Check directly in PhosphorIcons
    else if (PhosphorIcons[name]) {
      IconComponent = PhosphorIcons[name]
    }
  }

  // Fallback to Info icon if not found
  if (!IconComponent) {
    IconComponent = PhosphorIcons.Info || 'span'
  }

  const isCustom = typeof IconComponent === 'function' && Object.values(CustomIcons).includes(IconComponent)

  const renderedIcon = isCustom ? (
    <IconComponent size={size} className={className} style={style} {...rest} />
  ) : (
    <IconComponent
      size={size}
      weight={weight}
      className={className}
      style={{ verticalAlign: 'middle', flexShrink: 0, ...style }}
      {...rest}
    />
  )

  if (chip) {
    return (
      <span
        className="app-icon-chip"
        style={{
          width: chipSize,
          height: chipSize,
          borderRadius: chipRadius,
          display: 'grid',
          placeItems: 'center',
          background: 'rgba(229, 169, 60, 0.08)',
          color: 'var(--accent, #E5A93C)',
          flexShrink: 0,
        }}
      >
        {renderedIcon}
      </span>
    )
  }

  return renderedIcon
}
