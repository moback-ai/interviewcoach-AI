import React from "react";
import { useTheme } from "@/hooks/useTheme";

const ThemedImage = ({ lightSrc, darkSrc, alt = "", className = "" }) => {
  const { isDark } = useTheme();

  return (
    <img
      src={isDark ? darkSrc : lightSrc}
      alt={alt}
      className={className}
    />
  );
};

export default ThemedImage;
