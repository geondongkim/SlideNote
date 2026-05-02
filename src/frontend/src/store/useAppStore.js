import { create } from 'zustand'

export const useAppStore = create((set) => ({
  fileId: null,
  pageCount: 0,
  currentSlide: 1,
  setFile: (fileId, pageCount) => set({ fileId, pageCount, currentSlide: 1 }),
  setCurrentSlide: (page) => set({ currentSlide: page }),
}))
