import { apiFetch } from './client'
import type {
  ValidationReportResponse,
  ValidationStrategyResponse,
  ValidationRegimeResponse,
  ValidationSectorResponse,
} from './types'

export function fetchValidationReport(): Promise<ValidationReportResponse> {
  return apiFetch<ValidationReportResponse>('/api/validation/report')
}

export function fetchValidationByStrategy(): Promise<ValidationStrategyResponse> {
  return apiFetch<ValidationStrategyResponse>('/api/validation/report/by-strategy')
}

export function fetchValidationByRegime(): Promise<ValidationRegimeResponse> {
  return apiFetch<ValidationRegimeResponse>('/api/validation/report/by-regime')
}

export function fetchValidationBySector(): Promise<ValidationSectorResponse> {
  return apiFetch<ValidationSectorResponse>('/api/validation/report/by-sector')
}
