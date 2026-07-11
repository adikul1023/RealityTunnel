/**
 * Centralized Application Configuration
 * All public URLs and environment configurations must be accessed through this module.
 */

export const config = {
  /**
   * Oracle Billing & Authentication API URL
   * Production: https://api.stealthy.co.in
   */
  apiUrl: process.env.NEXT_PUBLIC_API_URL || 'https://api.stealthy.co.in',

  /**
   * Customer Marketing & Portal Main Site
   * Production: https://stealthy.co.in
   */
  mainSiteUrl: process.env.NEXT_PUBLIC_MAIN_SITE || 'https://stealthy.co.in',

  /**
   * Client Downloads Base URL
   * Production: https://downloads.stealthy.co.in
   */
  downloadUrl: process.env.NEXT_PUBLIC_DOWNLOAD_URL || 'https://downloads.stealthy.co.in',

  /**
   * Support Contact Email
   */
  supportEmail: process.env.NEXT_PUBLIC_SUPPORT_EMAIL || 'support@stealthy.co.in',

  /**
   * System Status & Maintenance Page URL
   */
  statusPageUrl: process.env.NEXT_PUBLIC_STATUS_PAGE || 'https://status.stealthy.co.in',
} as const;
