import type { CSSProperties, ReactNode } from "react";

interface IconProps {
  size?: number;
  fill?: string;
  stroke?: string;
  sw?: number;
  style?: CSSProperties;
}

const Icon = ({
  d,
  size = 14,
  fill = "none",
  stroke = "currentColor",
  sw = 1.5,
  style,
}: IconProps & { d: string | ReactNode }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 16 16"
    fill={fill}
    stroke={stroke}
    strokeWidth={sw}
    strokeLinecap="round"
    strokeLinejoin="round"
    style={style}
  >
    {typeof d === "string" ? <path d={d} /> : d}
  </svg>
);

export const Icons = {
  Search: (p: IconProps) => <Icon {...p} d="M7 12.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11Zm6 2-2.2-2.2" />,
  Filter: (p: IconProps) => <Icon {...p} d="M2 3h12l-4.5 6V14l-3-1.5V9L2 3Z" />,
  Play: (p: IconProps) => <Icon {...p} d="M4.5 3v10l8-5-8-5Z" fill="currentColor" stroke="none" />,
  Refresh: (p: IconProps) => <Icon {...p} d="M2.5 8a5.5 5.5 0 0 1 9.6-3.6L13.5 5.5M13.5 8a5.5 5.5 0 0 1-9.6 3.6L2.5 10.5M13.5 2.5v3h-3M2.5 13.5v-3h3" />,
  Sparkle: (p: IconProps) => <Icon {...p} d="M8 2.5v3M8 10.5v3M2.5 8h3M10.5 8h3M4 4l1.5 1.5M10.5 10.5 12 12M12 4l-1.5 1.5M5.5 10.5 4 12" />,
  Check: (p: IconProps) => <Icon {...p} d="M3 8.5 6.5 12 13 4.5" />,
  X: (p: IconProps) => <Icon {...p} d="M3.5 3.5 12.5 12.5M12.5 3.5 3.5 12.5" />,
  Chevron: (p: IconProps) => <Icon {...p} d="M5 6.5 8 9.5 11 6.5" />,
  ChevronR: (p: IconProps) => <Icon {...p} d="M6 4.5 9.5 8 6 11.5" />,
  Lock: (p: IconProps) => <Icon {...p} d="M4.5 7V5.5a3.5 3.5 0 0 1 7 0V7M3.5 7h9v6.5h-9z" />,
  Link: (p: IconProps) => <Icon {...p} d="M7 4H4.5A2.5 2.5 0 0 0 2 6.5v3A2.5 2.5 0 0 0 4.5 12H7M9 4h2.5A2.5 2.5 0 0 1 14 6.5v3a2.5 2.5 0 0 1-2.5 2.5H9M5.5 8h5" />,
  Doc: (p: IconProps) => <Icon {...p} d="M3.5 2h6L13 5.5V14H3.5V2Zm6 0v3.5H13" />,
  Folder: (p: IconProps) => <Icon {...p} d="M2 4.5h4l1 1.5h7v7H2v-8.5Z" />,
  Bot: (p: IconProps) => <Icon {...p} d="M5 7h6v5H5zM6.5 7V4.5h3V7M3 9h2M11 9h2M7 9.5v.5M9 9.5v.5" />,
  User: (p: IconProps) => <Icon {...p} d="M8 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM3 13.5c.5-2 2.5-3 5-3s4.5 1 5 3" />,
  Plus: (p: IconProps) => <Icon {...p} d="M8 3v10M3 8h10" />,
  Db: (p: IconProps) => <Icon {...p} d="M2.5 4c0-1.1 2.5-2 5.5-2s5.5.9 5.5 2-2.5 2-5.5 2-5.5-.9-5.5-2Zm0 0v8c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2V4M2.5 8c0 1.1 2.5 2 5.5 2s5.5-.9 5.5-2" />,
  Cell: (p: IconProps) => <Icon {...p} d="M2 3h12v10H2zM2 8h12M7 3v10" />,
  Shield: (p: IconProps) => <Icon {...p} d="M8 2 3 4v4c0 3 2 5 5 6 3-1 5-3 5-6V4L8 2Z" />,
  Eye: (p: IconProps) => <Icon {...p} d="M1.5 8s2.5-4.5 6.5-4.5S14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8Z M8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" />,
  Clock: (p: IconProps) => <Icon {...p} d="M8 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12ZM8 4.5V8l2.5 1.5" />,
  Copy: (p: IconProps) => <Icon {...p} d="M5.5 5.5h7v8h-7zM5.5 5.5V3.5h-3v8h3" />,
  Download: (p: IconProps) => <Icon {...p} d="M8 2v8M5 7l3 3 3-3M3 13h10" />,
  Trash: (p: IconProps) => <Icon {...p} d="M3 4.5h10M5.5 4.5V3a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1.5M4.5 4.5v8.5a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1V4.5M6.5 7v4.5M9.5 7v4.5" />,
};

export type IconName = keyof typeof Icons;
