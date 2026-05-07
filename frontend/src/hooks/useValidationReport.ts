import { useQuery } from '@tanstack/react-query'
import {
  fetchValidationReport,
  fetchValidationByStrategy,
  fetchValidationByRegime,
  fetchValidationBySector,
} from '@/api/validation'

export function useValidationReport() {
  return useQuery({
    queryKey: ['validation', 'report'],
    queryFn: fetchValidationReport,
    staleTime: 60_000,
  })
}

export function useValidationByStrategy() {
  return useQuery({
    queryKey: ['validation', 'by-strategy'],
    queryFn: fetchValidationByStrategy,
    staleTime: 60_000,
  })
}

export function useValidationByRegime() {
  return useQuery({
    queryKey: ['validation', 'by-regime'],
    queryFn: fetchValidationByRegime,
    staleTime: 60_000,
  })
}

export function useValidationBySector() {
  return useQuery({
    queryKey: ['validation', 'by-sector'],
    queryFn: fetchValidationBySector,
    staleTime: 60_000,
  })
}
