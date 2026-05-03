import { create } from 'zustand'

export const useAppStore = create((set) => ({
  fileId: null,
  pageCount: 0,
  currentSlide: 1,
  filename: '',
  setFile: (fileId, pageCount, filename = '') => set({ fileId, pageCount, currentSlide: 1, filename }),
  setCurrentSlide: (page) => set({ currentSlide: page }),
  setPageCount: (pageCount) => set({ pageCount }),
  clearFile: () => set({ fileId: null, pageCount: 0, currentSlide: 1, filename: '' }),
}))
